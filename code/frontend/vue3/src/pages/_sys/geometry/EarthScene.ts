/**
 * Babylon 地球场景封装
 *
 * 功能:
 *  - 贴图地球 + 经纬网格线(世界场景)
 *  - 球面拾取: 点击获取经纬度(WGS84)
 *  - 点/线/面绘制交互(单击加点, 双击/按钮结束, 实时预览)
 *  - 已保存要素渲染(点=标记球, 线=大圆弧线, 面=切平面 earcut 裁剪填充)
 *  - 相机定位飞行(聚焦某要素)
 */
import {
  AbstractMesh,
  Animation,
  ArcRotateCamera,
  Color3,
  Color4,
  Engine,
  HemisphericLight,
  Matrix,
  Mesh,
  MeshBuilder,
  PointLight,
  PointerEventTypes,
  PolygonMeshBuilder,
  Quaternion,
  Scene,
  StandardMaterial,
  Texture,
  Vector3,
} from 'babylonjs'
import earcut from 'earcut'
import earthImg from '@/assets/img/earth_0.png'
import type { GeoFeature, LngLat } from '@/types/geometry'

/** 绘制模式 */
export type DrawMode = 'none' | 'point' | 'linestring' | 'polygon'

/** 绘制事件回调参数 */
export interface DrawEvent {
  mode: DrawMode
  /** 当前已收集的顶点(经纬度) */
  points: LngLat[]
  /** 是否已完成(画点=单击即完成; 线/面=双击或调用 finishDraft) */
  finished: boolean
}

/** 地球半径(单位任意, 内部统一) */
const EARTH_RADIUS = 2
/** 要素/预览相对球面的抬升比例(避免 z-fighting) */
const LIFT = 1.004

class EarthScene {
  canvas: HTMLCanvasElement
  engine: Engine
  scene: Scene
  camera: ArcRotateCamera
  earthMesh: Mesh

  /** 已保存要素的 mesh 集合(要素ID -> mesh列表, 便于删除) */
  private featureMeshes = new Map<string, AbstractMesh[]>()
  /** 绘制预览 mesh 列表 */
  private draftMeshes: AbstractMesh[] = []
  /** 绘制中已收集的顶点 */
  private draftPoints: LngLat[] = []
  /** 当前绘制模式 */
  private drawMode: DrawMode = 'none'
  /** 绘制事件回调 */
  private onDrawCallback: ((e: DrawEvent) => void) | null = null
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
    this._initGridLines()
    this._initPointer()
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
    camera.lowerRadiusLimit = EARTH_RADIUS * 1.15
    camera.upperRadiusLimit = EARTH_RADIUS * 8
    camera.wheelDeltaPercentage = 0.01
    camera.panningSensibility = 0 // 禁平移, 始终围绕地心
    camera.attachControl(this.canvas, true)
    return camera
  }

  /** 灯光(半球光 + 正面点光) */
  private _initLights(): void {
    new HemisphericLight('hemi', new Vector3(0, 1, 0), this.scene).intensity = 0.55
    const sun = new PointLight('sun', new Vector3(6, 3, 6), this.scene)
    sun.intensity = 0.9
  }

  /** 贴图地球 */
  private _initEarth(): Mesh {
    const earth = MeshBuilder.CreateSphere(
      'earth',
      { diameter: EARTH_RADIUS * 2, segments: 64 },
      this.scene,
    )
    const material = new StandardMaterial('earthMat', this.scene)
    material.diffuseTexture = new Texture(earthImg, this.scene)
    material.specularColor = new Color3(0.08, 0.1, 0.08)
    earth.material = material
    return earth
  }

  /** 经纬网格线(每30度, 淡绿色装饰) */
  private _initGridLines(): void {
    const lines: Vector3[][] = []
    const step = 30
    // 经线
    for (let lon = -180; lon < 180; lon += step) {
      const pts: Vector3[] = []
      for (let lat = -90; lat <= 90; lat += 5) {
        pts.push(EarthScene.latLonToVector3(lat, lon, EARTH_RADIUS * 1.001))
      }
      lines.push(pts)
    }
    // 纬线
    for (let lat = -60; lat <= 60; lat += step) {
      const pts: Vector3[] = []
      for (let lon = -180; lon <= 180; lon += 5) {
        pts.push(EarthScene.latLonToVector3(lat, lon, EARTH_RADIUS * 1.001))
      }
      lines.push(pts)
    }
    const grid = MeshBuilder.CreateLineSystem('grid', { lines }, this.scene)
    grid.color = new Color3(0.45, 0.72, 0.55)
    grid.isPickable = false
    grid.alpha = 0.5
  }

  /** 指针事件(点击拾取球面经纬度) */
  private _initPointer(): void {
    this.pointerObserver = this.scene.onPointerObservable.add((pi) => {
      if (pi.type !== PointerEventTypes.POINTERTAP) return
      if (this.drawMode === 'none') return
      // 仅命中地球本体(要素 mesh 均不可拾取, 点击可穿透)
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

  // ################ 经纬度 <-> 3D 坐标 ################

  /** 经纬度转球面坐标(与球体 UV 贴图对齐) */
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

  /** 结束当前线/面绘制(由页面"完成"按钮调用) */
  finishDraft(): void {
    if (this.drawMode === 'linestring' && this.draftPoints.length >= 2) {
      this.onDrawCallback?.({
        mode: this.drawMode,
        points: [...this.draftPoints],
        finished: true,
      })
    }
    else if (this.drawMode === 'polygon' && this.draftPoints.length >= 3) {
      this.onDrawCallback?.({
        mode: this.drawMode,
        points: [...this.draftPoints],
        finished: true,
      })
    }
    this.clearDraft()
  }

  /** 清除未完成的绘制预览 */
  clearDraft(): void {
    this.draftPoints = []
    this.draftMeshes.forEach((m) => m.dispose())
    this.draftMeshes = []
  }

  /** 点击处理: 加点/双击结束 */
  private _handleTap(lngLat: LngLat, isDoubleTap: boolean): void {
    if (this.drawMode === 'point') {
      // 画点: 单击即完成
      this.draftPoints = [lngLat]
      this._renderDraftMarker(lngLat)
      this.onDrawCallback?.({
        mode: this.drawMode,
        points: [lngLat],
        finished: true,
      })
      this.clearDraft()
      return
    }

    if (isDoubleTap) {
      // 双击: 移除双击误加的重复点后结束
      if (this.draftPoints.length > 1) this.draftPoints.pop()
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

  /** 重绘绘制预览(顶点 + 边界线) */
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
      // 面绘制时自动闭合预览
      if (this.drawMode === 'polygon') {
        path.push(...this._buildArcPath([this.draftPoints[this.draftPoints.length - 1], this.draftPoints[0]]))
      }
      const line = MeshBuilder.CreateLines('draft_line', { points: path }, this.scene)
      line.color = new Color3(0.95, 0.62, 0.2)
      line.isPickable = false
      this.draftMeshes.push(line)
    }
  }

  /** 画点时的临时大标记(完成前预览) */
  private _renderDraftMarker(lngLat: LngLat): void {
    const marker = this._createMarkerMesh(
      'draft_point',
      lngLat,
      new Color3(0.95, 0.62, 0.2),
      0.05,
    )
    this.draftMeshes.push(marker)
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

  /** 渲染单个要素 */
  renderFeature(feature: GeoFeature): void {
    const meshes: AbstractMesh[] = []
    const color = this._featureColor(feature.feature_type)

    if (feature.geometry.type === 'Point') {
      const [lon, lat] = feature.geometry.coordinates as number[]
      meshes.push(
        this._createMarkerMesh(`f_${feature.id}_p`, { lon, lat }, color, 0.032),
      )
    }
    else if (feature.geometry.type === 'LineString') {
      const pts = feature.geometry.coordinates as number[][]
      const path = this._buildArcPath(pts.map(([lon, lat]) => ({ lon, lat })))
      const line = MeshBuilder.CreateLines(`f_${feature.id}_l`, { points: path }, this.scene)
      line.color = color
      line.isPickable = false
      meshes.push(line)
      // 顶点小标记
      pts.forEach(([lon, lat], i) => {
        meshes.push(
          this._createMarkerMesh(`f_${feature.id}_v${i}`, { lon, lat }, color, 0.018),
        )
      })
    }
    else if (feature.geometry.type === 'Polygon') {
      const ring = (feature.geometry.coordinates as number[][][])[0] ?? []
      // 去掉闭合重复点
      const pts = ring.length > 1 && ring[0][0] === ring[ring.length - 1][0]
        && ring[0][1] === ring[ring.length - 1][1]
        ? ring.slice(0, -1)
        : ring
      const lngLats = pts.map(([lon, lat]) => ({ lon, lat }))
      // 半透明填充面
      const polygonMesh = this._createPolygonMesh(`f_${feature.id}_poly`, lngLats, color)
      if (polygonMesh) meshes.push(polygonMesh)
      // 边界线
      const path = this._buildArcPath(lngLats)
      if (lngLats.length > 2) {
        path.push(...this._buildArcPath([lngLats[lngLats.length - 1], lngLats[0]]))
      }
      const line = MeshBuilder.CreateLines(`f_${feature.id}_l`, { points: path }, this.scene)
      line.color = color
      line.isPickable = false
      meshes.push(line)
      // 顶点小标记
      lngLats.forEach((lngLat, i) => {
        meshes.push(
          this._createMarkerMesh(`f_${feature.id}_v${i}`, lngLat, color, 0.018),
        )
      })
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

  /** 要素类型对应颜色(点红/线蓝/面绿, 自然笔记风) */
  private _featureColor(featureType: string): Color3 {
    switch (featureType) {
      case 'point': return new Color3(0.85, 0.33, 0.3)
      case 'linestring': return new Color3(0.25, 0.55, 0.9)
      case 'polygon': return new Color3(0.35, 0.72, 0.45)
      default: return new Color3(0.5, 0.5, 0.5)
    }
  }

  /** 创建球面标记小球 */
  private _createMarkerMesh(
    name: string,
    lngLat: LngLat,
    color: Color3,
    diameter: number,
  ): Mesh {
    const marker = MeshBuilder.CreateSphere(name, { diameter, segments: 12 }, this.scene)
    marker.position = EarthScene.latLonToVector3(lngLat.lat, lngLat.lon, EARTH_RADIUS * LIFT)
    const material = new StandardMaterial(`${name}_mat`, this.scene)
    material.diffuseColor = color
    material.emissiveColor = color.scale(0.55)
    marker.material = material
    marker.isPickable = false
    return marker
  }

  /** 经纬度点列转大圆弧路径(每段细分16份) */
  private _buildArcPath(points: LngLat[]): Vector3[] {
    if (points.length === 0) return []
    if (points.length === 1) {
      return [EarthScene.latLonToVector3(points[0].lat, points[0].lon, EARTH_RADIUS * LIFT)]
    }
    const path: Vector3[] = []
    for (let i = 0; i < points.length - 1; i++) {
      const a = EarthScene.latLonToVector3(points[i].lat, points[i].lon, EARTH_RADIUS * LIFT)
      const b = EarthScene.latLonToVector3(points[i + 1].lat, points[i + 1].lon, EARTH_RADIUS * LIFT)
      const seg = this._slerpPoints(a, b, 16)
      // 去掉与前段重复的衔接点
      if (i > 0) seg.shift()
      path.push(...seg)
    }
    return path
  }

  /**
   * 球面多边形渲染: 顶点投影到中心切平面, earcut 裁剪生成半透明面
   */
  private _createPolygonMesh(name: string, lngLats: LngLat[], color: Color3): Mesh | null {
    if (lngLats.length < 3) return null
    const radius = EARTH_RADIUS * (LIFT + 0.002)

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
    const contour = lngLats.map((p, i) => {
      const pt = EarthScene.latLonToVector3(p.lat, p.lon, radius)
      return new Vector3(Vector3.Dot(pt, u), Vector3.Dot(pt, v), 0)
    })

    const builder = new PolygonMeshBuilder(name, contour, this.scene, earcut)
    const mesh = builder.build()
    const material = new StandardMaterial(`${name}_mat`, this.scene)
    material.diffuseColor = color
    material.emissiveColor = color.scale(0.25)
    material.alpha = 0.32
    material.backFaceCulling = false
    mesh.material = material
    mesh.isPickable = false

    // 旋转对齐切平面(局部 X->u, Y->v, Z->n), 平移到切点
    // 行向量约定: 局部 X 轴 (1,0,0)*M = 第一行 = u
    const rot = Matrix.FromValues(
      u.x, u.y, u.z, 0,
      v.x, v.y, v.z, 0,
      n.x, n.y, n.z, 0,
      0, 0, 0, 1,
    )
    mesh.rotationQuaternion = Quaternion.FromRotationMatrix(rot)
    mesh.position = c
    return mesh
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
