/**
 * Babylon 地球场景封装(卡通风格点阵地球)
 *
 * 功能:
 *  - 卡通风格球体: 亮蓝海洋 + 绿色陆地散点(内置极简全球边界 GeoJSON 实时点内采样) + 轮廓描边
 *  - 图层系统: 全球边界散点(world)与要素图层分组渲染, 支持显隐切换(setLayerVisible)
 *  - 球面拾取: 点击获取经纬度(WGS84), 绘制时指针悬停实时显示坐标
 *  - 点/线/面/立体物绘制交互(单击加点, 双击/按钮结束, 撤销由页面调用 undoDraftPoint)
 *  - 面填充为球面共形网格(经纬度空间 earcut + 递归细分 + 投影球面), 贴合地表无切平面翘边;
 *    边界先按大圆弧加密(与描边管同路径), 面与边线重合无缝隙
 *  - 立体物为球面棱柱: 顶盖球面网格沿法向抬升, 侧壁沿边界大圆弧生成, 无多余竖直面
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
  Mesh,
  MeshBuilder,
  PointsCloudSystem,
  PointerEventTypes,
  PointLight,
  Scene,
  StandardMaterial,
  VertexData,
  Vector3,
} from 'babylonjs'
import earcut from 'earcut'
import worldLand from '../assets/world-land-110m.json'
import { DEFAULT_LAYER_ID, WORLD_LAYER_ID, featureLayerOf, resolveStyle, type GeoFeature, type GeoFeatureStyle, type LngLat } from '../types'

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
/** 陆地散点基础间距(度) */
const DOT_STEP_DEG = 0.9
/** 面网格细分目标边长(度, 经度按纬度余弦加权) */
const SUBDIV_DEG = 1.5
/** 面网格细分最大递归深度(防止超大面顶点爆炸) */
const SUBDIV_MAX_DEPTH = 4
/** 侧壁边界弧线细分段数 */
const WALL_SEGMENTS = 12
/** 面边界大圆弧加密段数(与描边管线路径一致, 保证面边界与边线重合无缝隙) */
const RING_DENSE_SEGMENTS = 16

/** 归一化陆地多边形(外环+洞; 经度连续化后的 [lon,lat] 环 + 包围盒) */
interface LandPolygon {
  rings: number[][][]
  minLon: number
  maxLon: number
  minLat: number
  maxLat: number
}

class EarthScene {
  canvas: HTMLCanvasElement
  engine: Engine
  scene: Scene
  camera: ArcRotateCamera
  earthMesh: Mesh

  /** 已保存要素的 mesh 集合(要素ID -> mesh列表, 便于删除) */
  private featureMeshes = new Map<string, AbstractMesh[]>()
  /** 要素归属图层(要素ID -> 图层ID, 来自 properties.layer) */
  private featureLayerOf = new Map<string, string>()
  /** 图层可见性(未记录的图层默认可见) */
  private layerVisibility = new Map<string, boolean>()
  /** 陆地散点 mesh(内置 world 图层) */
  private landDotsMesh: Mesh | null = null
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

  // ################ 内置图层: 全球边界散点 ################

  /**
   * 陆地散点(内置 world 图层): 用极简全球边界 GeoJSON 实时做点内采样,
   * 在陆地区域按等积密度生成绿色散点(替代旧掩膜图方案, 州域形状准确)。
   */
  private async _initLandDots(): Promise<void> {
    try {
      const positions = EarthScene.sampleLandDotPositions()
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
      mesh.setEnabled(this.layerVisible(WORLD_LAYER_ID))
      this.landDotsMesh = mesh
    }
    catch (error) {
      console.warn('陆地散点生成失败, 仅显示纯色球体:', error)
    }
  }

  /**
   * 采样陆地散点球面坐标(GeoJSON 点内判定)
   * 纬度环按 cos(lat) 加密经度采样保证密度均匀(极区不过密),
   * 每个多边形只在其包围盒经度范围内扫描, 避免全球遍历。
   */
  static sampleLandDotPositions(): Vector3[] {
    const polys = EarthScene.buildLandPolygons()
    const positions: Vector3[] = []
    for (let lat = -83; lat <= 83; lat += DOT_STEP_DEG) {
      // 每纬度环的经度步长与 cos(lat) 成反比(纬向收缩补偿)
      const lonStep = DOT_STEP_DEG / Math.max(0.12, Math.cos((lat * Math.PI) / 180))
      for (const poly of polys) {
        if (lat < poly.minLat - DOT_STEP_DEG || lat > poly.maxLat + DOT_STEP_DEG) continue
        // 与全球网格同相位取经度采样点, 再做点内判定
        const start = Math.ceil(poly.minLon / lonStep) * lonStep
        for (let lon = start; lon <= poly.maxLon; lon += lonStep) {
          if (EarthScene.isLandPoint(poly, lon, lat)) {
            // 归一化位移后的经度(如 190)与 360° 周期投影到同一球面点
            positions.push(EarthScene.latLonToVector3(lat, lon, EARTH_RADIUS * 1.002))
          }
        }
      }
    }
    return positions
  }

  /** 解析内置 GeoJSON 为归一化陆地多边形列表(Polygon/MultiPolygon 兼容) */
  private static buildLandPolygons(): LandPolygon[] {
    const polys: LandPolygon[] = []
    for (const f of worldLand.features) {
      const g = f.geometry
      if (!g) continue
      const groups: number[][][][] = g.type === 'Polygon'
        ? [g.coordinates as unknown as number[][][]]
        : g.type === 'MultiPolygon'
          ? (g.coordinates as unknown as number[][][][])
          : []
      for (const rings of groups) {
        if (!rings.length || rings[0].length < 4) continue
        const outer = EarthScene.normalizeRing(rings[0])
        const normalized: number[][][] = [outer]
        for (let i = 1; i < rings.length; i++) normalized.push(EarthScene.normalizeRing(rings[i]))
        const xs = outer.map(p => p[0])
        const ys = outer.map(p => p[1])
        polys.push({
          rings: normalized,
          minLon: Math.min(...xs),
          maxLon: Math.max(...xs),
          minLat: Math.min(...ys),
          maxLat: Math.max(...ys),
        })
      }
    }
    return polys
  }

  /** 经度连续化: 相邻顶点经度差收敛到 ±180 内(跨 180° 多边形正确采样/三角化) */
  private static normalizeRing(ring: number[][]): number[][] {
    const out: number[][] = [[ring[0][0], ring[0][1]]]
    let prev = ring[0][0]
    for (let i = 1; i < ring.length; i++) {
      let lon = ring[i][0]
      while (lon - prev > 180) lon -= 360
      while (lon - prev < -180) lon += 360
      out.push([lon, ring[i][1]])
      prev = lon
    }
    return out
  }

  /** 奇偶规则点内判定(射线法) */
  static pointInRing(lon: number, lat: number, ring: number[][]): boolean {
    let inside = false
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0]
      const yi = ring[i][1]
      const xj = ring[j][0]
      const yj = ring[j][1]
      if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
        inside = !inside
      }
    }
    return inside
  }

  /** 判定点是否在陆地多边形内(任意外环内 且 不在所有洞内) */
  private static isLandPoint(poly: LandPolygon, lon: number, lat: number): boolean {
    if (!EarthScene.pointInRing(lon, lat, poly.rings[0])) return false
    for (let i = 1; i < poly.rings.length; i++) {
      if (EarthScene.pointInRing(lon, lat, poly.rings[i])) return false
    }
    return true
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

  /**
   * 经纬度转球面坐标(经度 360° 周期: lon 与 lon±360 映射到同一点)
   * 注意: Babylon 默认左手坐标系, 不能直接套用 three.js 右手系公式
   * (x 取负会导致东西经镜像), 此处 x 不取负保证大陆形状方向正确。
   */
  static latLonToVector3(lat: number, lon: number, radius: number): Vector3 {
    const phi = ((90 - lat) * Math.PI) / 180
    const theta = ((lon + 180) * Math.PI) / 180
    return new Vector3(
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.cos(phi),
      radius * Math.sin(phi) * Math.sin(theta),
    )
  }

  /** 球面坐标转经纬度(与 latLonToVector3 严格互逆) */
  static vector3ToLatLon(point: Vector3): LngLat {
    const r = point.length()
    const lat = 90 - (Math.acos(point.y / r) * 180) / Math.PI
    let lon = (Math.atan2(point.z, point.x) * 180) / Math.PI - 180
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

  /** 单位方向球面插值(侧壁边界弧线细分用) */
  private _slerpDir(a: Vector3, b: Vector3, t: number): Vector3 {
    const dot = Math.min(1, Math.max(-1, Vector3.Dot(a, b)))
    const omega = Math.acos(dot)
    if (omega < 1e-6) return a.clone()
    const so = Math.sin(omega)
    return a
      .scale(Math.sin((1 - t) * omega) / so)
      .add(b.scale(Math.sin(t * omega) / so))
      .normalize()
  }

  /**
   * 多边形边界大圆弧加密(转回经纬度): 与描边管线路径完全一致
   * (同 slerp、同段数), 保证面边界与边线中心线重合, 消除面/线缝隙。
   * @param lngLats 相邻点间加密的折线点列(不自动闭合)
   */
  private _densifyLngLats(lngLats: LngLat[], segments = RING_DENSE_SEGMENTS): LngLat[] {
    if (lngLats.length < 2) return [...lngLats]
    const out: LngLat[] = []
    for (let i = 0; i < lngLats.length - 1; i++) {
      const a = EarthScene.latLonToVector3(lngLats[i].lat, lngLats[i].lon, 1)
      const b = EarthScene.latLonToVector3(lngLats[i + 1].lat, lngLats[i + 1].lon, 1)
      const seg = this._slerpPoints(a, b, segments)
      if (i > 0) seg.shift() // 去掉与前段重复的衔接点
      for (const p of seg) out.push(EarthScene.vector3ToLatLon(p))
    }
    return out
  }

  // ################ 图层显隐 ################

  /** 当前图层是否可见(未记录默认可见) */
  layerVisible(layer: string): boolean {
    return this.layerVisibility.get(layer) ?? true
  }

  /** 切换图层显隐(world=内置边界散点; 其余按 properties.layer 过滤要素) */
  setLayerVisible(layer: string, visible: boolean): void {
    this.layerVisibility.set(layer, visible)
    if (layer === WORLD_LAYER_ID) this.landDotsMesh?.setEnabled(visible)
    for (const [id, ly] of this.featureLayerOf) {
      if (ly === layer) this.featureMeshes.get(id)?.forEach((m) => m.setEnabled(visible))
    }
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
        // 立体物: 球面棱柱(顶盖抬升 + 边界侧壁) + 顶缘描边
        this.draftMeshes.push(
          ...this._createExtrudedMesh('draft_x', this.draftPoints, color, style.opacity, height, style.width),
        )
      }
      else {
        // 平面: 球面共形填充 + 描边
        const polygonMesh = this._createSphericalPatch(
          'draft_poly', this.draftPoints, EARTH_RADIUS * LIFT,
        )
        if (polygonMesh) {
          polygonMesh.material = this._flatMaterial('draft_poly_mat', color, style.opacity)
          this.draftMeshes.push(polygonMesh)
        }
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
   * 全量渲染已保存要素(先清空旧 mesh), 按 properties.layer 分组并应用图层显隐
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
        // 立体物: 球面棱柱(style.height > 0)
        meshes.push(
          ...this._createExtrudedMesh(`f_${feature.id}_x`, lngLats, color, style.opacity, height, style.width),
        )
      }
      else {
        // 平面: 球面共形填充面(贴合地表)
        const polygonMesh = this._createSphericalPatch(
          `f_${feature.id}_poly`, lngLats, EARTH_RADIUS * LIFT,
        )
        if (polygonMesh) {
          polygonMesh.material = this._flatMaterial(`f_${feature.id}_poly_mat`, color, style.opacity)
          meshes.push(polygonMesh)
        }
        // 描边
        if (lngLats.length > 2) {
          meshes.push(
            this._createTubeLine(`f_${feature.id}_l`, [...lngLats, lngLats[0]], color, 0.0045 * style.width, style.opacity),
          )
        }
      }
    }

    // 按归属图层应用显隐
    const layer = featureLayerOf(feature)
    this.featureLayerOf.set(feature.id, layer)
    if (!this.layerVisible(layer)) meshes.forEach((m) => m.setEnabled(false))
    this.featureMeshes.set(feature.id, meshes)
  }

  /** 删除单个要素的渲染 mesh */
  removeFeature(featureId: string): void {
    const meshes = this.featureMeshes.get(featureId)
    meshes?.forEach((m) => m.dispose())
    this.featureMeshes.delete(featureId)
    this.featureLayerOf.delete(featureId)
  }

  /** 清空全部要素渲染 */
  clearFeatures(): void {
    for (const meshes of this.featureMeshes.values()) {
      meshes.forEach((m) => m.dispose())
    }
    this.featureMeshes.clear()
    this.featureLayerOf.clear()
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

  /** 管状线渲染(卡通平涂, 样式化线宽; radius 可指定抬升半径) */
  private _createTubeLine(
    name: string,
    lngLats: LngLat[],
    color: Color3,
    radius: number,
    opacity = 1,
    liftRadius = EARTH_RADIUS * LIFT,
  ): Mesh {
    const path = this._buildArcPath(lngLats, liftRadius)
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

  /** 经纬度点列转大圆弧路径(每段细分16份, liftRadius 为球面抬升半径) */
  private _buildArcPath(points: LngLat[], liftRadius = EARTH_RADIUS * LIFT): Vector3[] {
    if (points.length === 0) return []
    if (points.length === 1) {
      return [EarthScene.latLonToVector3(points[0].lat, points[0].lon, liftRadius)]
    }
    const path: Vector3[] = []
    for (let i = 0; i < points.length - 1; i++) {
      const a = EarthScene.latLonToVector3(points[i].lat, points[i].lon, liftRadius)
      const b = EarthScene.latLonToVector3(points[i + 1].lat, points[i + 1].lon, liftRadius)
      const seg = this._slerpPoints(a, b, 16)
      // 去掉与前段重复的衔接点
      if (i > 0) seg.shift()
      path.push(...seg)
    }
    return path
  }

  /**
   * 球面共形多边形填充: 经纬度空间 earcut 三角化后递归细分,
   * 全部顶点投影到球面 → 填充面贴合地表弯曲, 无切平面翘边/穿模。
   * @param lngLats 多边形顶点(未闭合)
   * @param radius 球面半径(含抬升量)
   */
  private _createSphericalPatch(name: string, lngLats: LngLat[], radius: number): Mesh | null {
    if (lngLats.length < 3) return null

    // 边界先按大圆弧加密(含闭合边)再三角化: 面边界与描边管线走同一路径, 无缝隙
    const closed = [...lngLats, lngLats[0]]
    const dense = this._densifyLngLats(closed)
    dense.pop() // 去掉与首点重复的闭合点(earcut 隐式闭合)

    // 经度连续化(跨 180° 多边形可正确三角化; 投影具有 360° 周期性, 位移经度映射同一球面点)
    const ring = EarthScene.normalizeLngLats(dense)
    const flat: number[] = []
    for (const p of ring) flat.push(p[0], p[1])
    const triIndices = earcut(flat, null, 2)
    if (!triIndices.length) return null

    // 逐三角形递归细分后投影球面(三角形汤: 每 3 个顶点一个三角形)
    const positions: number[] = []
    for (let t = 0; t < triIndices.length; t += 3) {
      this._emitPatchTriangle(
        ring[triIndices[t]], ring[triIndices[t + 1]], ring[triIndices[t + 2]],
        0, radius, positions,
      )
    }
    if (!positions.length) return null

    const mesh = new Mesh(name, this.scene)
    const vd = new VertexData()
    vd.positions = positions
    const idx: number[] = []
    for (let i = 0; i < positions.length / 3; i += 3) idx.push(i, i + 1, i + 2)
    vd.indices = idx
    const normals: number[] = []
    VertexData.ComputeNormals(positions, idx, normals)
    vd.normals = normals
    vd.applyToMesh(mesh)
    mesh.isPickable = false
    return mesh
  }

  /** 经纬度点列经度连续化(供三角化/侧壁生成; 投影周期性保证位移经度渲染一致) */
  private static normalizeLngLats(lngLats: LngLat[]): number[][] {
    const out: number[][] = [[lngLats[0].lon, lngLats[0].lat]]
    let prev = lngLats[0].lon
    for (let i = 1; i < lngLats.length; i++) {
      let lon = lngLats[i].lon
      while (lon - prev > 180) lon -= 360
      while (lon - prev < -180) lon += 360
      out.push([lon, lngLats[i].lat])
      prev = lon
    }
    return out
  }

  /** 三角形递归细分(经纬度空间, 边长按纬度余弦加权)后投影球面并输出顶点 */
  private _emitPatchTriangle(
    a: number[],
    b: number[],
    c: number[],
    depth: number,
    radius: number,
    out: number[],
  ): void {
    const edgeDeg = (p: number[], q: number[]) => {
      const cosLat = Math.cos((((p[1] + q[1]) / 2) * Math.PI) / 180)
      return Math.hypot((p[0] - q[0]) * cosLat, p[1] - q[1])
    }
    const span = Math.max(edgeDeg(a, b), edgeDeg(b, c), edgeDeg(c, a))
    if (span <= SUBDIV_DEG || depth >= SUBDIV_MAX_DEPTH) {
      const pa = EarthScene.latLonToVector3(a[1], a[0], radius)
      const pb = EarthScene.latLonToVector3(b[1], b[0], radius)
      const pc = EarthScene.latLonToVector3(c[1], c[0], radius)
      out.push(pa.x, pa.y, pa.z, pb.x, pb.y, pb.z, pc.x, pc.y, pc.z)
      return
    }
    // 中点细分(经纬度线性中点)
    const mid = (p: number[], q: number[]): number[] => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2]
    const ab = mid(a, b)
    const bc = mid(b, c)
    const ca = mid(c, a)
    this._emitPatchTriangle(a, ab, ca, depth + 1, radius, out)
    this._emitPatchTriangle(ab, b, bc, depth + 1, radius, out)
    this._emitPatchTriangle(ca, bc, c, depth + 1, radius, out)
    this._emitPatchTriangle(ab, bc, ca, depth + 1, radius, out)
  }

  /**
   * 立体物渲染(球面棱柱): 顶盖为球面网格片沿法向抬升 height,
   * 侧壁沿边界大圆弧在 底环(rBase) 与 顶环(rTop) 间生成四边形条带,
   * 顶缘描边闭合管。整体贴合球面弯曲, 无多余竖直面。
   * 返回 [顶盖, 侧壁, 顶缘描边] 三组 mesh(卡通平涂, 侧面深一号颜色增强立体感)
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
    const rBase = EARTH_RADIUS * LIFT
    const rTop = rBase + height
    const meshes: AbstractMesh[] = []

    // ---- 顶盖: 球面共形网格片(rTop) ----
    const cap = this._createSphericalPatch(`${name}_cap`, lngLats, rTop)
    if (cap) {
      cap.material = this._flatMaterial(`${name}_cap_mat`, color, opacity)
      meshes.push(cap)
    }

    // ---- 侧壁: 边界弧线细分, 每个细分方向 d 上连接 d*rBase 与 d*rTop ----
    const ring = EarthScene.normalizeLngLats(lngLats)
    const positions: number[] = []
    const indices: number[] = []
    let base = 0
    const count = ring.length
    for (let i = 0; i < count; i++) {
      const a = EarthScene.latLonToVector3(ring[i][1], ring[i][0], 1).normalize()
      const j = (i + 1) % count
      const b = EarthScene.latLonToVector3(ring[j][1], ring[j][0], 1).normalize()
      for (let s = 0; s <= WALL_SEGMENTS; s++) {
        const d = this._slerpDir(a, b, s / WALL_SEGMENTS)
        positions.push(d.x * rBase, d.y * rBase, d.z * rBase, d.x * rTop, d.y * rTop, d.z * rTop)
        if (s > 0) {
          const p = base + (s - 1) * 2
          indices.push(p, p + 1, p + 3, p, p + 3, p + 2)
        }
      }
      base += (WALL_SEGMENTS + 1) * 2
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
    meshes.push(walls)

    // ---- 顶缘描边: 顶环大圆弧闭合成管, 深色粗边(卡通描边) ----
    const rimLngLats = [...lngLats, lngLats[0]]
    const rim = this._createTubeLine(`${name}_rim`, rimLngLats, color.scale(0.55), Math.max(0.003, 0.0045 * width), 1, rTop)
    rim.name = `${name}_rim`
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
