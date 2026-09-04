/**
 * Babylon 地球场景封装(卡通风格点阵地球)
 *
 * 功能:
 *  - 卡通风格球体: 亮蓝海洋 + 绿色陆地散点(Web Mercator 掩膜采样) + 轮廓描边
 *  - 球面拾取: 点击获取经纬度(WGS84), 绘制时指针悬停实时显示坐标
 *  - 点/线/面/立体物绘制交互(单击加点, 双击/按钮结束, 撤销由页面调用 undoDraftPoint)
 *  - 已保存要素渲染(样式化: 点=标记球, 线=管状线, 面=切平面填充+描边,
 *    立体物=面沿法线拉伸棱柱, 高度存于 style.height)
 *  - 相机定位飞行(聚焦某要素); 拉近不穿帮: 近裁剪面远小于最近观察距离,
 *    相机下限保持在球外, 任何缩放级别都能看到地表
 */
import {
  AbstractMesh,
  Animation,
  ArcRotateCamera,
  CloudPoint,
  Color3,
  Color4,
  Engine,
  FresnelParameters,
  HemisphericLight,
  Matrix,
  Mesh,
  MeshBuilder,
  PointLight,
  PointsCloudSystem,
  PointerEventTypes,
  PolygonMeshBuilder,
  Quaternion,
  Scene,
  StandardMaterial,
  VertexData,
  Vector3,
} from 'babylonjs'
import earcut from 'earcut'
import earthMaskImg from '@/assets/img/earth_0.png'
import { resolveStyle, type GeoFeature, type GeoFeatureStyle, type LngLat } from '../types'

/** 绘制模式(extrude=立体物: 绘制底面后按 style.height 拉伸) */
export type DrawMode = 'none' | 'point' | 'linestring' | 'polygon' | 'extrude'

/** 绘制事件回调参数 */
export interface DrawEvent {
  mode: DrawMode
  /** 当前已收集的顶点(经纬度) */
  points: LngLat[]
  /** 是否已完成(画点=单击即完成; 线/面/立体=双击或调用 finishDraft) */
  finished: boolean
}

/** 地球半径(单位任意, 内部统一) */
const EARTH_RADIUS = 2
/** 要素/预览相对球面的抬升比例(避免 z-fighting) */
const LIFT = 1.004
/** 陆地掩膜判定阈值(R 通道, 白色陆地 > 205, 青色海洋 < 180) */
const LAND_THRESHOLD = 205
/** 陆地散点基础间距(度) */
const DOT_STEP_DEG = 1.1

class EarthScene {
  canvas: HTMLCanvasElement
  engine: Engine
  scene: Scene
  camera: ArcRotateCamera
  earthMesh: Mesh

  /** 已保存要素的 mesh 集合(要素ID -> mesh列表, 便于删除) */
  private featureMeshes = new Map<string, AbstractMesh[]>()
  /** 绘制预览 mesh 列表(进行中描边 + 完成后成品预览共用) */
  private draftMeshes: AbstractMesh[] = []
  /** 绘制中已收集的顶点 */
  private draftPoints: LngLat[] = []
  /** 当前绘制模式 */
  private drawMode: DrawMode = 'none'
  /** 绘制是否已完成(等待保存, 保留成品预览直到保存/取消) */
  private draftFinished = false
  /** 成品预览所用样式(保存对话框实时同步, 保证所见即所得) */
  private draftStyle: Required<GeoFeatureStyle> = resolveStyle('polygon')
  /** 绘制事件回调 */
  private onDrawCallback: ((e: DrawEvent) => void) | null = null
  /** 悬停事件回调(绘制模式下指针所指地表经纬度) */
  private onHoverCallback: ((p: LngLat | null) => void) | null = null
  /** 悬停跟随的幽灵标记 */
  private ghostMarker: Mesh | null = null
  /** 双击检测状态 */
  private lastTapTime = 0
  private lastTapX = 0
  private lastTapY = 0
  /** resize 监听 */
  private resizeObserver: ResizeObserver | null = null
  /** 指针事件句柄 */
  private pointerObserver: unknown

  constructor(canvasId: string) {
    this.canvas = document.getElementById(canvasId) as HTMLCanvasElement
    this.engine = new Engine(this.canvas, true, {
      preserveDrawingBuffer: true,
      stencil: true,
    })
    this.scene = new Scene(this.engine)
    this.scene.clearColor = new Color4(0.04, 0.09, 0.08, 1) // 深墨绿背景
    this.engine.runRenderLoop(() => this.scene.render())

    this.camera = this._initCamera()
    this._initLights()
    this.earthMesh = this._initEarth()
    // 异步生成陆地散点(不阻塞场景交互)
    this._initLandDots()
    this._initPointer()

    // 初始画布可能为 0 尺寸(样式异步注入), 延迟两帧强制校正渲染缓冲
    requestAnimationFrame(() => {
      this.engine.resize()
      requestAnimationFrame(() => this.engine.resize())
    })

    // 开发模式暴露实例, 便于控制台调试与自动化测试(如验证拉近深度)
    if (import.meta.env.DEV) {
      (window as unknown as Record<string, unknown>).__earthScene = this
    }
  }

  // ################ 基础场景 ################

  /** 轨道相机(绕地球旋转/缩放) */
  private _initCamera(): ArcRotateCamera {
    const camera = new ArcRotateCamera(
      'camera',
      -Math.PI / 2,
      Math.PI / 2.6,
      EARTH_RADIUS * 2.6,
      Vector3.Zero(),
      this.scene,
    )
    // 深度修复: 默认 minZ=1 会大于"贴近地表时相机到球面的距离",
    // 导致近裁剪面切进球体看到球内。取远小于最近观察距离的值即可。
    camera.minZ = 0.01
    camera.lowerRadiusLimit = EARTH_RADIUS * 1.03 // 允许贴近地表, 同时保证相机始终在球外
    camera.upperRadiusLimit = EARTH_RADIUS * 8
    camera.wheelDeltaPercentage = 0.01
    camera.panningSensibility = 0 // 禁平移, 始终围绕地心
    camera.attachControl(this.canvas, true)
    return camera
  }

  /** 灯光(半球光 + 正面点光, 高环境光弱化阴影 → 卡通少阴影观感) */
  private _initLights(): void {
    new HemisphericLight('hemi', new Vector3(0, 1, 0), this.scene).intensity = 0.65
    const sun = new PointLight('sun', new Vector3(6, 3, 6), this.scene)
    sun.intensity = 0.8
  }

  /** 卡通风格球体(亮蓝海洋, 暗部提亮, 白色边缘微光, 轮廓描边) */
  private _initEarth(): Mesh {
    const earth = MeshBuilder.CreateSphere(
      'earth',
      { diameter: EARTH_RADIUS * 2, segments: 96 },
      this.scene,
    )
    const ocean = Color3.FromHexString('#4dabf7')
    const material = new StandardMaterial('earthMat', this.scene)
    material.diffuseColor = ocean
    material.specularColor = Color3.Black()
    // 暗部提亮(自发光打底), 弱化明暗过渡 → 卡通平涂感
    material.emissiveColor = ocean.scale(0.42)
    // 边缘菲涅尔提亮(正面=1 不变, 掠射角加亮 → 贴纸式亮边)
    material.emissiveFresnelParameters = new FresnelParameters()
    material.emissiveFresnelParameters.bias = 0.35
    material.emissiveFresnelParameters.power = 3
    material.emissiveFresnelParameters.leftColor = new Color3(1.5, 1.55, 1.6)
    material.emissiveFresnelParameters.rightColor = new Color3(1, 1, 1)
    earth.material = material
    // 卡通轮廓剪影(深一号的蓝)
    earth.outlineColor = new Color3(0.1, 0.3, 0.48)
    earth.outlineWidth = 0.02
    return earth
  }

  /**
   * 陆地散点(卡通配色): 读取陆地掩膜图, 按等积密度采样陆地区域,
   * 以 PointsCloudSystem 渲染绿色散点模拟陆地。
   * 注: 掩膜图为 Web Mercator 投影, 需按墨卡托公式反算纵坐标。
   */
  private async _initLandDots(): Promise<void> {
    try {
      const positions = await EarthScene.sampleLandDotPositions()
      if (!positions.length) return

      const pcs = new PointsCloudSystem('landDots', 2.4, this.scene)
      pcs.addPoints(positions.length, (particle: CloudPoint, i: number) => {
        particle.position = positions[i]
        particle.color = new Color4(0.55, 0.91, 0.6, 1) // 嫩绿陆地
      })
      const mesh = await pcs.buildMeshAsync()
      const material = mesh.material as StandardMaterial
      material.emissiveColor = new Color3(1, 1, 1) // 点云不受光照, 恒定显示粒子色
      material.diffuseColor = Color3.Black()
      material.specularColor = Color3.Black()
      material.alpha = 0.85
      material.disableLighting = true
      mesh.isPickable = false
    }
    catch (error) {
      console.warn('陆地散点生成失败, 仅显示纯色球体:', error)
    }
  }

  /**
   * 采样陆地散点球面坐标
   * 纬度环按 cos(lat) 加密经度采样, 保证球面散点密度均匀(极区不过密)
   */
  static async sampleLandDotPositions(): Promise<Vector3[]> {
    const mask = await EarthScene.loadLandMask()
    if (!mask) return []
    const positions: Vector3[] = []
    for (let lat = -83; lat <= 83; lat += DOT_STEP_DEG) {
      // 每纬度环的经度步长与 cos(lat) 成反比(墨卡托纬向收缩补偿)
      const lonStep = DOT_STEP_DEG / Math.max(0.12, Math.cos((lat * Math.PI) / 180))
      for (let lon = -180; lon < 180; lon += lonStep) {
        if (EarthScene.isLand(mask, lat, lon)) {
          positions.push(EarthScene.latLonToVector3(lat, lon, EARTH_RADIUS * 1.002))
        }
      }
    }
    return positions
  }

  /** 加载陆地掩膜图到离屏画布(Web Mercator 投影, 256x256) */
  private static async loadLandMask(): Promise<ImageData | null> {
    const img = new Image()
    img.src = earthMaskImg
    await img.decode()
    const canvas = document.createElement('canvas')
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    ctx.drawImage(img, 0, 0)
    return ctx.getImageData(0, 0, canvas.width, canvas.height)
  }

  /** 判定经纬度是否为陆地(掩膜图 Web Mercator 纵坐标反算) */
  static isLand(mask: ImageData, lat: number, lon: number): boolean {
    const { width, height, data } = mask
    const x = Math.min(width - 1, Math.max(0, Math.floor(((lon + 180) / 360) * width)))
    // Web Mercator: y = (1/2 - ln(tan(π/4 + lat/2)) / 2π), 纬度越往两极越拉伸
    const clampedLat = Math.min(85, Math.max(-85, lat))
    const mercY
      = 0.5 - Math.log(Math.tan(Math.PI / 4 + (clampedLat * Math.PI) / 360)) / (2 * Math.PI)
    const y = Math.min(height - 1, Math.max(0, Math.floor(mercY * height)))
    const idx = (y * width + x) * 4
    return data[idx] > LAND_THRESHOLD // R 通道: 白色陆地/青色海洋
  }

  /** 指针事件(点击拾取球面经纬度 + 移动悬停跟随) */
  private _initPointer(): void {
    this.pointerObserver = this.scene.onPointerObservable.add((pi) => {
      if (pi.type === PointerEventTypes.POINTERMOVE) {
        this._handleHover()
        return
      }
      if (pi.type !== PointerEventTypes.POINTERTAP) return
      if (this.drawMode === 'none') return
      // 仅命中地球本体(要素/散点 mesh 均不可拾取, 点击可穿透)
      const pick = this.scene.pick(
        this.scene.pointerX,
        this.scene.pointerY,
        (mesh) => mesh === this.earthMesh,
      )
      if (!pick?.hit || !pick.pickedPoint) return

      // 双击检测(300ms 内两次近似位置点击)
      const now = performance.now()
      const isDoubleTap
        = now - this.lastTapTime < 300
          && Math.abs(this.scene.pointerX - this.lastTapX) < 6
          && Math.abs(this.scene.pointerY - this.lastTapY) < 6
      this.lastTapTime = now
      this.lastTapX = this.scene.pointerX
      this.lastTapY = this.scene.pointerY

      const lngLat = EarthScene.vector3ToLatLon(pick.pickedPoint)
      this._handleTap(lngLat, isDoubleTap)
    })
  }

  /** 悬停跟随: 绘制模式下在指针所指地表位置显示幽灵标记并回调坐标 */
  private _handleHover(): void {
    if (this.drawMode === 'none') {
      this._hideGhost()
      this.onHoverCallback?.(null)
      return
    }
    const pick = this.scene.pick(
      this.scene.pointerX,
      this.scene.pointerY,
      (mesh) => mesh === this.earthMesh,
    )
    if (!pick?.hit || !pick.pickedPoint) {
      this._hideGhost()
      this.onHoverCallback?.(null)
      return
    }
    const lngLat = EarthScene.vector3ToLatLon(pick.pickedPoint)
    if (!this.ghostMarker) {
      this.ghostMarker = this._createMarkerMesh(
        'hover_ghost', { lon: 0, lat: 0 }, new Color3(1, 1, 1), 0.024, 0.65,
      )
    }
    this.ghostMarker.setEnabled(true)
    this.ghostMarker.position = EarthScene.latLonToVector3(
      lngLat.lat, lngLat.lon, EARTH_RADIUS * (LIFT + 0.004),
    )
    this.onHoverCallback?.(lngLat)
  }

  /** 隐藏悬停幽灵标记 */
  private _hideGhost(): void {
    this.ghostMarker?.setEnabled(false)
  }

  // ################ 经纬度 <-> 3D 坐标 ################

  /** 经纬度转球面坐标 */
  static latLonToVector3(lat: number, lon: number, radius: number): Vector3 {
    const phi = ((90 - lat) * Math.PI) / 180
    const theta = ((lon + 180) * Math.PI) / 180
    return new Vector3(
      -radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.cos(phi),
      radius * Math.sin(phi) * Math.sin(theta),
    )
  }

  /** 球面坐标转经纬度 */
  static vector3ToLatLon(point: Vector3): LngLat {
    const r = point.length()
    const lat = 90 - (Math.acos(point.y / r) * 180) / Math.PI
    let lon = (Math.atan2(point.z, -point.x) * 180) / Math.PI - 180
    if (lon < -180) lon += 360
    if (lon > 180) lon -= 360
    return { lon, lat }
  }

  /** 球面大圆插值(两点间弧线细分) */
  private _slerpPoints(a: Vector3, b: Vector3, segments: number): Vector3[] {
    const na = a.clone().normalize()
    const nb = b.clone().normalize()
    const dot = Math.min(1, Math.max(-1, Vector3.Dot(na, nb)))
    const omega = Math.acos(dot)
    const pts: Vector3[] = []
    if (omega < 1e-6) return [a.clone(), b.clone()]
    const so = Math.sin(omega)
    for (let i = 0; i <= segments; i++) {
      const t = i / segments
      const p = na
        .scale(Math.sin((1 - t) * omega) / so)
        .add(nb.scale(Math.sin(t * omega) / so))
      pts.push(p.scale(a.length()))
    }
    return pts
  }

  // ################ 绘制交互 ################

  /**
   * 设置绘制模式并注册回调
   * @param mode 绘制模式(none 表示浏览)
   * @param cb 每次顶点变化/完成时回调
   */
  setDrawMode(mode: DrawMode, cb: ((e: DrawEvent) => void) | null = null): void {
    this.drawMode = mode
    this.onDrawCallback = cb
    this.clearDraft()
  }

  /** 设置悬停坐标回调(绘制模式下指针在地表移动时触发) */
  setHoverCallback(cb: ((p: LngLat | null) => void) | null = null): void {
    this.onHoverCallback = cb
  }

  /** 结束当前线/面/立体绘制(由页面"完成"按钮或双击触发), 保留成品预览 */
  finishDraft(): void {
    const minPoints = this.drawMode === 'linestring' ? 2 : 3
    if (
      (this.drawMode === 'linestring' || this.drawMode === 'polygon' || this.drawMode === 'extrude')
      && this.draftPoints.length >= minPoints
    ) {
      this.draftFinished = true
      this._renderFinalPreview()
      this.onDrawCallback?.({
        mode: this.drawMode,
        points: [...this.draftPoints],
        finished: true,
      })
    }
  }

  /** 撤销上一个顶点(仅进行中可用) */
  undoDraftPoint(): void {
    if (this.draftFinished || this.drawMode === 'none' || this.drawMode === 'point') return
    if (!this.draftPoints.length) return
    this.draftPoints.pop()
    this._refreshDraft()
    this.onDrawCallback?.({
      mode: this.drawMode,
      points: [...this.draftPoints],
      finished: false,
    })
  }

  /** 保存对话框样式变化时同步更新成品预览(所见即所得) */
  updateDraftPreview(style: Required<GeoFeatureStyle>): void {
    this.draftStyle = style
    if (this.draftFinished && this.draftPoints.length) this._renderFinalPreview()
  }

  /** 清除未完成的绘制预览与成品预览 */
  clearDraft(): void {
    this.draftPoints = []
    this.draftFinished = false
    this.draftMeshes.forEach((m) => m.dispose())
    this.draftMeshes = []
    this._hideGhost()
  }

  /** 点击处理: 加点/双击结束 */
  private _handleTap(lngLat: LngLat, isDoubleTap: boolean): void {
    if (this.drawMode === 'point') {
      // 画点: 单击即完成(保留成品预览直到保存/取消)
      this.draftPoints = [lngLat]
      this.draftFinished = true
      this._renderFinalPreview()
      this.onDrawCallback?.({
        mode: this.drawMode,
        points: [lngLat],
        finished: true,
      })
      return
    }

    if (isDoubleTap) {
      // 双击结束: 首次点击已加入该顶点, 此处不重复加点也不丢点, 直接结束
      this.finishDraft()
      return
    }

    this.draftPoints.push(lngLat)
    this._refreshDraft()
    this.onDrawCallback?.({
      mode: this.drawMode,
      points: [...this.draftPoints],
      finished: false,
    })
  }

  /** 重绘进行中的绘制预览(顶点 + 边界线) */
  private _refreshDraft(): void {
    this.draftMeshes.forEach((m) => m.dispose())
    this.draftMeshes = []

    // 顶点标记
    for (let i = 0; i < this.draftPoints.length; i++) {
      const p = this.draftPoints[i]
      const marker = this._createMarkerMesh(
        `draft_p_${i}`,
        p,
        new Color3(0.95, 0.62, 0.2),
        0.03,
      )
      this.draftMeshes.push(marker)
    }

    // 边界线(>=2 个点)
    if (this.draftPoints.length >= 2) {
      const path = this._buildArcPath(this.draftPoints)
      // 面/立体绘制时自动闭合预览
      if (this.drawMode !== 'linestring') {
        path.push(...this._buildArcPath([this.draftPoints[this.draftPoints.length - 1], this.draftPoints[0]]))
      }
      const line = MeshBuilder.CreateLines('draft_line', { points: path }, this.scene)
      line.color = new Color3(0.95, 0.62, 0.2)
      line.isPickable = false
      this.draftMeshes.push(line)
    }
  }

  /** 成品预览: 按当前样式渲染与保存后一致的最终效果(所见即所得) */
  private _renderFinalPreview(): void {
    this.draftMeshes.forEach((m) => m.dispose())
    this.draftMeshes = []

    const style = this.draftStyle
    const color = this._hexColor(style.color, Color3.FromHexString('#ffd43b'))

    if (this.drawMode === 'point' && this.draftPoints[0]) {
      this.draftMeshes.push(
        this._createMarkerMesh('draft_point', this.draftPoints[0], color, 0.045 * style.width, style.opacity),
      )
    }
    else if (this.drawMode === 'linestring' && this.draftPoints.length >= 2) {
      this.draftMeshes.push(
        this._createTubeLine('draft_line', this.draftPoints, color, 0.006 * style.width, style.opacity),
      )
    }
    else if (this.drawMode === 'polygon' || this.drawMode === 'extrude') {
      const height = this.drawMode === 'extrude' ? Math.max(0.005, style.height) : 0
      if (height > 0) {
        // 立体物: 底面拉伸棱柱 + 顶缘描边
        this.draftMeshes.push(
          ...this._createExtrudedMesh('draft_x', this.draftPoints, color, style.opacity, height, style.width),
        )
      }
      else {
        // 平面: 半透明填充 + 描边
        const polygonMesh = this._createPolygonMesh('draft_poly', this.draftPoints, color, style.opacity)
        if (polygonMesh) this.draftMeshes.push(polygonMesh)
        if (this.draftPoints.length > 2) {
          this.draftMeshes.push(
            this._createTubeLine(
              'draft_line',
              [...this.draftPoints, this.draftPoints[0]],
              color, 0.0045 * style.width, style.opacity,
            ),
          )
        }
      }
    }
  }

  // ################ 要素渲染 ################

  /**
   * 全量渲染已保存要素(先清空旧 mesh)
   * @param features 后端返回的要素列表
   */
  renderFeatures(features: GeoFeature[]): void {
    this.clearFeatures()
    for (const f of features) this.renderFeature(f)
  }

  /** 渲染单个要素(已存在时先移除旧渲染) */
  renderFeature(feature: GeoFeature): void {
    this.removeFeature(feature.id)
    const meshes: AbstractMesh[] = []
    const style = resolveStyle(feature.feature_type, feature.style)
    const color = this._hexColor(style.color, Color3.FromHexString('#ffd43b'))

    if (feature.geometry.type === 'Point') {
      const [lon, lat] = feature.geometry.coordinates as number[]
      meshes.push(
        this._createMarkerMesh(`f_${feature.id}_p`, { lon, lat }, color, 0.034 * style.width, style.opacity),
      )
    }
    else if (feature.geometry.type === 'LineString') {
      const pts = feature.geometry.coordinates as number[][]
      const lngLats = pts.map(([lon, lat]) => ({ lon, lat }))
      meshes.push(
        this._createTubeLine(`f_${feature.id}_l`, lngLats, color, 0.006 * style.width, style.opacity),
      )
    }
    else if (feature.geometry.type === 'Polygon') {
      const ring = (feature.geometry.coordinates as number[][][])[0] ?? []
      // 去掉闭合重复点
      const pts = ring.length > 1 && ring[0][0] === ring[ring.length - 1][0]
        && ring[0][1] === ring[ring.length - 1][1]
        ? ring.slice(0, -1)
        : ring
      const lngLats = pts.map(([lon, lat]) => ({ lon, lat }))
      const height = Math.max(0, style.height ?? 0)
      if (height > 0.001 && lngLats.length > 2) {
        // 立体物: 底面拉伸棱柱(style.height > 0)
        meshes.push(
          ...this._createExtrudedMesh(`f_${feature.id}_x`, lngLats, color, style.opacity, height, style.width),
        )
      }
      else {
        // 平面: 半透明填充面
        const polygonMesh = this._createPolygonMesh(`f_${feature.id}_poly`, lngLats, color, style.opacity)
        if (polygonMesh) meshes.push(polygonMesh)
        // 描边
        if (lngLats.length > 2) {
          meshes.push(
            this._createTubeLine(`f_${feature.id}_l`, [...lngLats, lngLats[0]], color, 0.0045 * style.width, style.opacity),
          )
        }
      }
    }

    this.featureMeshes.set(feature.id, meshes)
  }

  /** 删除单个要素的渲染 mesh */
  removeFeature(featureId: string): void {
    const meshes = this.featureMeshes.get(featureId)
    meshes?.forEach((m) => m.dispose())
    this.featureMeshes.delete(featureId)
  }

  /** 清空全部要素渲染 */
  clearFeatures(): void {
    for (const meshes of this.featureMeshes.values()) {
      meshes.forEach((m) => m.dispose())
    }
    this.featureMeshes.clear()
  }

  /** 相机飞行聚焦要素(看向要素中心上空) */
  focusFeature(feature: GeoFeature): void {
    const pts: LngLat[] = []
    if (feature.geometry.type === 'Point') {
      const [lon, lat] = feature.geometry.coordinates as number[]
      pts.push({ lon, lat })
    }
    else if (feature.geometry.type === 'LineString') {
      ;(feature.geometry.coordinates as number[][]).forEach(([lon, lat]) =>
        pts.push({ lon, lat }))
    }
    else {
      const ring = (feature.geometry.coordinates as number[][][])[0] ?? []
      ring.forEach(([lon, lat]) => pts.push({ lon, lat }))
    }
    if (!pts.length) return

    // 中心经纬度
    const centerLat = pts.reduce((s, p) => s + p.lat, 0) / pts.length
    const centerLon = pts.reduce((s, p) => s + p.lon, 0) / pts.length
    const n = EarthScene.latLonToVector3(centerLat, centerLon, 1)

    // 目标: 相机位于中心方向上空
    const targetBeta = Math.acos(Math.min(1, Math.max(-1, n.y)))
    let targetAlpha = Math.atan2(n.z, n.x)
    // alpha 走最短路径
    while (targetAlpha - this.camera.alpha > Math.PI) targetAlpha -= Math.PI * 2
    while (targetAlpha - this.camera.alpha < -Math.PI) targetAlpha += Math.PI * 2
    const targetRadius = EARTH_RADIUS * 2.2

    Animation.CreateAndStartAnimation(
      'cam_alpha', this.camera, 'alpha', 60, 40,
      this.camera.alpha, targetAlpha, Animation.ANIMATIONLOOPMODE_CONSTANT,
    )
    Animation.CreateAndStartAnimation(
      'cam_beta', this.camera, 'beta', 60, 40,
      this.camera.beta, targetBeta, Animation.ANIMATIONLOOPMODE_CONSTANT,
    )
    Animation.CreateAndStartAnimation(
      'cam_radius', this.camera, 'radius', 60, 40,
      this.camera.radius, targetRadius, Animation.ANIMATIONLOOPMODE_CONSTANT,
    )
  }

  // ################ 渲染辅助 ################

  /** 安全解析 HEX 颜色(数据库 style 值异常时回退默认色, 不中断渲染) */
  private _hexColor(hex: string, fallback: Color3): Color3 {
    try {
      return Color3.FromHexString(hex)
    }
    catch {
      return fallback
    }
  }

  /** 卡通平涂材质(不受光照, 恒定显示主色) */
  private _flatMaterial(name: string, color: Color3, opacity = 1): StandardMaterial {
    const material = new StandardMaterial(name, this.scene)
    material.disableLighting = true
    material.emissiveColor = color
    material.diffuseColor = Color3.Black()
    material.specularColor = Color3.Black()
    material.alpha = Math.min(1, Math.max(0.05, opacity))
    material.backFaceCulling = false // 双面渲染, 立体物内壁/翻转面不消失
    return material
  }

  /** 创建球面标记小球(卡通平涂+深色描边, 样式: 颜色/大小/透明度) */
  private _createMarkerMesh(
    name: string,
    lngLat: LngLat,
    color: Color3,
    diameter: number,
    opacity = 1,
  ): Mesh {
    const marker = MeshBuilder.CreateSphere(name, { diameter, segments: 12 }, this.scene)
    marker.position = EarthScene.latLonToVector3(lngLat.lat, lngLat.lon, EARTH_RADIUS * (LIFT + 0.002))
    marker.material = this._flatMaterial(`${name}_mat`, color, opacity)
    // 贴纸式深色描边
    marker.outlineColor = color.scale(0.45)
    marker.outlineWidth = 0.005
    marker.isPickable = false
    return marker
  }

  /** 管状线渲染(卡通平涂, 样式化线宽) */
  private _createTubeLine(
    name: string,
    lngLats: LngLat[],
    color: Color3,
    radius: number,
    opacity = 1,
  ): Mesh {
    const path = this._buildArcPath(lngLats)
    const tube = MeshBuilder.CreateTube(name, {
      path,
      radius: Math.max(0.002, radius),
      tessellation: 6,
      cap: Mesh.NO_CAP,
    }, this.scene)
    tube.material = this._flatMaterial(`${name}_mat`, color, opacity)
    tube.isPickable = false
    return tube
  }

  /** 经纬度点列转大圆弧路径(每段细分16份, radius 为球面抬升半径) */
  private _buildArcPath(points: LngLat[], radius = EARTH_RADIUS * LIFT): Vector3[] {
    if (points.length === 0) return []
    if (points.length === 1) {
      return [EarthScene.latLonToVector3(points[0].lat, points[0].lon, radius)]
    }
    const path: Vector3[] = []
    for (let i = 0; i < points.length - 1; i++) {
      const a = EarthScene.latLonToVector3(points[i].lat, points[i].lon, radius)
      const b = EarthScene.latLonToVector3(points[i + 1].lat, points[i + 1].lon, radius)
      const seg = this._slerpPoints(a, b, 16)
      // 去掉与前段重复的衔接点
      if (i > 0) seg.shift()
      path.push(...seg)
    }
    return path
  }

  /**
   * 计算多边形在中心切平面的局部坐标系与轮廓投影
   * 返回: 单位法向量 n, 切点 c, 局部->世界旋转矩阵 rot, 切平面轮廓点(局部 XY)
   */
  private _polygonFrame(lngLats: LngLat[], radius: number) {
    // 中心方向(顶点平均单位向量)
    const center = new Vector3(0, 0, 0)
    for (const p of lngLats) {
      center.addInPlace(EarthScene.latLonToVector3(p.lat, p.lon, 1))
    }
    const n = center.normalize()
    const c = n.scale(radius)

    // 切平面局部坐标系(u, v 垂直于 n)
    const ref = Math.abs(n.y) < 0.9 ? new Vector3(0, 1, 0) : new Vector3(1, 0, 0)
    const u = Vector3.Cross(n, ref).normalize()
    const v = Vector3.Cross(n, u)

    // 顶点投影到切平面(2D 轮廓)
    const contour = lngLats.map((p) => {
      const pt = EarthScene.latLonToVector3(p.lat, p.lon, radius)
      return new Vector3(Vector3.Dot(pt, u), Vector3.Dot(pt, v), 0)
    })

    // 旋转对齐切平面(局部 X->u, Y->v, Z->n)
    // 行向量约定: 局部 X 轴 (1,0,0)*M = 第一行 = u
    const rot = Matrix.FromValues(
      u.x, u.y, u.z, 0,
      v.x, v.y, v.z, 0,
      n.x, n.y, n.z, 0,
      0, 0, 0, 1,
    )
    return { n, c, rot, contour }
  }

  /**
   * 球面多边形渲染: 顶点投影到中心切平面, earcut 裁剪生成半透明填充面
   */
  private _createPolygonMesh(name: string, lngLats: LngLat[], color: Color3, opacity = 0.35): Mesh | null {
    if (lngLats.length < 3) return null
    const radius = EARTH_RADIUS * (LIFT + 0.001)

    const { c, rot, contour } = this._polygonFrame(lngLats, radius)
    const builder = new PolygonMeshBuilder(name, contour, this.scene, earcut)
    const mesh = builder.build()
    mesh.material = this._flatMaterial(`${name}_mat`, color, opacity)
    mesh.isPickable = false
    mesh.rotationQuaternion = Quaternion.FromRotationMatrix(rot)
    mesh.position = c
    return mesh
  }

  /**
   * 立体物渲染: 以多边形为底面, 沿切平面法线拉伸 height 生成棱柱
   * 返回 [侧壁, 顶盖, 顶缘描边] 三组 mesh(卡通平涂, 侧面用深一号颜色增强立体感)
   */
  private _createExtrudedMesh(
    name: string,
    lngLats: LngLat[],
    color: Color3,
    opacity: number,
    height: number,
    width = 1,
  ): AbstractMesh[] {
    if (lngLats.length < 3) return []
    const radius = EARTH_RADIUS * LIFT

    const { n, c, rot, contour } = this._polygonFrame(lngLats, radius)
    const meshes: AbstractMesh[] = []

    // ---- 顶盖: 轮廓平移到高度 h 后三角化 ----
    const cap = new PolygonMeshBuilder(`${name}_cap`, contour, this.scene, earcut).build()
    cap.material = this._flatMaterial(`${name}_cap_mat`, color, opacity)
    cap.isPickable = false
    cap.rotationQuaternion = Quaternion.FromRotationMatrix(rot)
    cap.position = c.add(n.scale(height))
    meshes.push(cap)

    // ---- 侧壁: 底环(z=0)与顶环(z=h)之间的四边形条带 ----
    const count = contour.length
    const positions: number[] = []
    for (const p of contour) positions.push(p.x, p.y, 0)
    for (const p of contour) positions.push(p.x, p.y, height)
    const indices: number[] = []
    for (let i = 0; i < count; i++) {
      const j = (i + 1) % count
      indices.push(i, j, j + count, i, j + count, i + count)
    }
    const walls = new Mesh(`${name}_wall`, this.scene)
    const vd = new VertexData()
    vd.positions = positions
    vd.indices = indices
    const normals: number[] = []
    VertexData.ComputeNormals(positions, indices, normals)
    vd.normals = normals
    vd.applyToMesh(walls)
    walls.material = this._flatMaterial(`${name}_wall_mat`, color.scale(0.78), opacity)
    walls.isPickable = false
    walls.rotationQuaternion = Quaternion.FromRotationMatrix(rot)
    walls.position = c
    meshes.push(walls)

    // ---- 顶缘描边: 顶环世界坐标闭合成管, 深色粗边(卡通描边) ----
    const topRing = contour.map((p) =>
      Vector3.TransformCoordinates(new Vector3(p.x, p.y, height), rot).add(c))
    const rim = MeshBuilder.CreateTube(`${name}_rim`, {
      path: [...topRing, topRing[0]],
      radius: Math.max(0.003, 0.0045 * width),
      tessellation: 6,
      cap: Mesh.NO_CAP,
    }, this.scene)
    rim.material = this._flatMaterial(`${name}_rim_mat`, color.scale(0.55), 1)
    rim.isPickable = false
    meshes.push(rim)

    return meshes
  }

  // ################ 生命周期 ################

  /** 监听容器尺寸变化自适应 */
  observeResize(domId: string): void {
    let timer: number | undefined
    this.resizeObserver = new ResizeObserver(() => {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => this.engine.resize(), 50)
    })
    const el = document.getElementById(domId)
    if (el) this.resizeObserver.observe(el)
  }

  /** 销毁场景(释放 WebGL 资源) */
  dispose(): void {
    this.resizeObserver?.disconnect()
    this.scene.onPointerObservable.remove(this.pointerObserver as never)
    this.engine.stopRenderLoop()
    this.scene.dispose()
    this.engine.dispose()
  }
}

export { EarthScene }
export type { GeoFeatureStyle }
