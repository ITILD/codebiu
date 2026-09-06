// src/modules/template/utils/FaceMeshScene.ts
import {
  Scene,
  Engine,
  Vector3,
  Color3,
  Color4,
  HemisphericLight,
  PointLight,
  ArcRotateCamera,
  Camera,
  Mesh,
  LinesMesh,
  VertexData,
  StandardMaterial,
  VertexBuffer,
  MeshBuilder,
} from 'babylonjs'

/** MediaPipe 特征点连线(start/end 为特征点索引) */
export interface LandmarkConnection {
  start: number
  end: number
}

/** 归一化人脸特征点(x/y ∈ [0,1], z 为相对深度) */
export interface NormalizedLandmark {
  x: number
  y: number
  z: number
}

/** 网格渲染模式: solid 实体(受光表面+网格线) / wire 线框 / points 点云 */
export type FaceMeshRenderMode = 'solid' | 'wire' | 'points'

/** 特征点归一化坐标 -> 场景坐标的缩放系数 */
const SCALE = 10

/**
 * 人脸特征网格 BabylonJS 场景
 * - 由 MediaPipe tesselation 连线构建三角网格(每 3 条连线为一个三角形的三条边, 顶点共享)
 * - 三个网格(实体/线框/点云)持有独立缓冲, updateLandmarks() 每帧分别提交同一份顶点数组, 不重建网格
 * - 实体模式 = 受光表面 + 线框网格叠加(呈现"特征网格"效果; 不用 EdgesRenderer, 因其描边几何
 *   在创建时按当时顶点烘焙, 而本场景顶点每帧变化, 描边会滞留在初始位置)
 * - 轮廓连线(眼/眉/唇/脸缘/虹膜)独立 LineSystem 高亮, 外扩 2% 避免与实体表面深度冲突
 * - 正交相机与视频画面同尺映射(初始正对画面, 网格可像素级叠加贴合视频人脸);
 *   拖动旋转/滚轮缩放自由查看三维, resetView() 复位恢复贴合
 */
class FaceMeshScene {
  canvas: HTMLCanvasElement
  engine: Engine
  scene: Scene
  camera!: ArcRotateCamera

  private solidMesh!: Mesh
  private wireMesh!: Mesh
  private pointsMesh!: Mesh
  private positions!: Float32Array
  private normals!: Float32Array
  private indices: number[] = []
  /** 轮廓连线定义(与 contourPoints 下标一一对应) */
  private contourConns: LandmarkConnection[] = []
  private contourPoints: Vector3[][] = []
  private contourLines: LinesMesh | undefined
  private resizeObserver: ResizeObserver | undefined
  private faceDetected = false
  private mode: FaceMeshRenderMode = 'solid'

  constructor(canvasId: string) {
    this.canvas = document.getElementById(canvasId) as HTMLCanvasElement
    this.engine = new Engine(this.canvas, true, {
      preserveDrawingBuffer: true,
      stencil: true,
    })
    this.scene = new Scene(this.engine)
    this.scene.clearColor = new Color4(0, 0, 0, 0) // 背景透明, 融入笔记卡片底色
    this._cameraInit()
    this._lightInit()
    // 循环渲染
    this.engine.runRenderLoop(() => {
      this.scene.render()
    })
  }

  /**
   * 由 tesselation 连线初始化人脸网格 + 轮廓高亮线
   * @param tesselation MediaPipe FACE_LANDMARKS_TESSELATION(每 3 条连线为一个三角形的三条边)
   * @param contours MediaPipe FACE_LANDMARKS_CONTOURS(五官轮廓连线集合)
   */
  initMesh(tesselation: LandmarkConnection[], contours: LandmarkConnection[]) {
    if (this.solidMesh) return
    // 478 个特征点, 顶点数据可更新(每帧原地改写)
    const pointCount = 478
    this.positions = new Float32Array(pointCount * 3)
    this.normals = new Float32Array(pointCount * 3)
    // 连线三元组 -> 共享顶点的三角形索引(a->b, b->c, c->a)
    const totalTriangles = Math.floor(tesselation.length / 3)
    for (let g = 0; g < totalTriangles; g++) {
      const a = tesselation[g * 3]
      const b = tesselation[g * 3 + 1]
      const c = tesselation[g * 3 + 2]
      if (a.end === b.start && b.end === c.start && c.end === a.start) {
        this.indices.push(a.start, a.end, b.end)
      }
    }
    if (this.indices.length === 0) {
      console.warn('FaceMeshScene: tesselation 连线三元组校验失败, 网格将退化为点云展示')
    }
    // 三个网格共享同一份顶点源数组, 各自持有独立 GPU 缓冲(每帧分别提交)
    const vertexData = new VertexData()
    vertexData.positions = this.positions
    vertexData.normals = this.normals
    vertexData.indices = this.indices
    this.solidMesh = new Mesh('faceSolid', this.scene)
    vertexData.applyToMesh(this.solidMesh, true)
    this.wireMesh = new Mesh('faceWire', this.scene)
    vertexData.applyToMesh(this.wireMesh, true)
    this.pointsMesh = new Mesh('facePoints', this.scene)
    vertexData.applyToMesh(this.pointsMesh, true)
    for (const m of [this.solidMesh, this.wireMesh, this.pointsMesh]) {
      m.isPickable = false
      // 顶点每帧形变, 包围盒不可靠: 永远参与渲染, 避免相机移动时被视锥剔除而消失
      m.alwaysSelectAsActiveMesh = true
    }
    // 实体材质: 青瓷玉感(淡青白瓷半透明 + 釉面高光), 双面渲染
    const faceMaterial = new StandardMaterial('faceMat', this.scene)
    faceMaterial.diffuseColor = Color3.FromHexString('#c9ded3')
    faceMaterial.emissiveColor = Color3.FromHexString('#233830')
    faceMaterial.specularColor = new Color3(0.4, 0.42, 0.4)
    faceMaterial.specularPower = 64
    faceMaterial.alpha = 0.88
    faceMaterial.backFaceCulling = false
    this.solidMesh.material = faceMaterial
    // 线框材质: 深青网格线(不受光, 纯色), 如玉面刻线
    const wireMaterial = new StandardMaterial('wireMat', this.scene)
    wireMaterial.wireframe = true
    wireMaterial.disableLighting = true
    wireMaterial.emissiveColor = Color3.FromHexString('#3f6b52')
    wireMaterial.alpha = 0.5
    wireMaterial.backFaceCulling = false
    this.wireMesh.material = wireMaterial
    // 点云材质: 亮青瓷特征点
    const pointsMaterial = new StandardMaterial('pointsMat', this.scene)
    pointsMaterial.pointsCloud = true
    pointsMaterial.pointSize = 6
    pointsMaterial.disableLighting = true
    pointsMaterial.emissiveColor = Color3.FromHexString('#a3cdb8')
    pointsMaterial.alpha = 0.9
    pointsMaterial.backFaceCulling = false
    this.pointsMesh.material = pointsMaterial
    // 半透明混合顺序: 表面先画, 网格线/点云叠上
    this.solidMesh.alphaIndex = 0
    this.wireMesh.alphaIndex = 1
    this.pointsMesh.alphaIndex = 1
    // 轮廓高亮线(眼/眉/唇/脸缘/虹膜), 每条连线为两点线段
    this.contourConns = contours
    this.contourPoints = contours.map(() => [new Vector3(0, 0, 0), new Vector3(0, 0, 0)])
    if (this.contourPoints.length) {
      this.contourLines = MeshBuilder.CreateLineSystem('contours', { lines: this.contourPoints, updatable: true }, this.scene)
      this.contourLines.color = Color3.FromHexString('#e07a5f')
      this.contourLines.isPickable = false
      this.contourLines.alwaysSelectAsActiveMesh = true
      this.contourLines.alphaIndex = 2 // 最后绘制
    }
    // 检测到人脸前先隐藏
    this.faceDetected = false
    this._applyVisibility()
  }

  /**
   * 更新特征点(每帧调用): 原地改写顶点/法线/轮廓线
   */
  updateLandmarks(landmarks: NormalizedLandmark[]) {
    if (!this.solidMesh || !landmarks || landmarks.length * 3 !== this.positions.length) return
    // 归一化坐标 -> 场景坐标:
    // X 取反(镜像), 与前置摄像头镜像画面方向一致; Y 取反(图像向下为正 -> 场景向上为正);
    // Z 原样(MediaPipe 朝相机为负, 相机位于 -z 侧, 鼻尖正对相机)
    for (let i = 0; i < landmarks.length; i++) {
      const lm = landmarks[i]
      const o = i * 3
      this.positions[o] = (0.5 - lm.x) * SCALE
      this.positions[o + 1] = (0.5 - lm.y) * SCALE
      this.positions[o + 2] = lm.z * SCALE
    }
    // 三个网格逐个提交同一份顶点(各自独立缓冲)
    this.solidMesh.updateVerticesData(VertexBuffer.PositionKind, this.positions)
    this.wireMesh.updateVerticesData(VertexBuffer.PositionKind, this.positions)
    this.pointsMesh.updateVerticesData(VertexBuffer.PositionKind, this.positions)
    // 法线仅实体受光模式需要; 线框/点云模式跳过以节省性能
    if (this.mode === 'solid') {
      VertexData.ComputeNormals(this.positions, this.indices, this.normals)
      this.solidMesh.updateVerticesData(VertexBuffer.NormalKind, this.normals)
    }
    // 轮廓线同步更新(整体外扩 2%, 浮在实体表面之上避免深度冲突被埋没)
    if (this.contourLines) {
      const k = SCALE * 1.02
      for (let i = 0; i < this.contourConns.length; i++) {
        const conn = this.contourConns[i]
        const from = landmarks[conn.start]
        const to = landmarks[conn.end]
        this.contourPoints[i][0].set((0.5 - from.x) * k, (0.5 - from.y) * k, from.z * k)
        this.contourPoints[i][1].set((0.5 - to.x) * k, (0.5 - to.y) * k, to.z * k)
      }
      MeshBuilder.CreateLineSystem('contours', { lines: this.contourPoints, instance: this.contourLines })
    }
    this.faceDetected = true
    this._applyVisibility()
  }

  /** 无人脸时隐藏全部网格 */
  clearFace() {
    if (!this.solidMesh) return
    this.faceDetected = false
    this._applyVisibility()
  }

  /** 切换渲染模式: 实体(表面+网格线) / 线框 / 点云 */
  setRenderMode(mode: FaceMeshRenderMode) {
    if (!this.solidMesh) return
    this.mode = mode
    this._applyVisibility()
  }

  /** 复位视角到初始贴合位(正对画面, 正交全幅) */
  resetView() {
    this.camera.alpha = -Math.PI / 2
    this.camera.beta = Math.PI / 2
    this.orthoScale = 1
    this._applyOrtho()
    this.camera.setTarget(Vector3.Zero())
  }

  /** 按当前模式与检测状态同步各网格显隐 */
  private _applyVisibility() {
    const m = this.mode
    this.solidMesh.setEnabled(this.faceDetected && m === 'solid')
    this.wireMesh.setEnabled(this.faceDetected && (m === 'solid' || m === 'wire'))
    this.pointsMesh.setEnabled(this.faceDetected && m === 'points')
    this.contourLines?.setEnabled(this.faceDetected)
  }

  /**
   * 监听容器尺寸变化自适应(与 BaseScene.observeInit 约定一致)
   */
  observeInit(domId: string) {
    let timer: number | undefined
    this.resizeObserver = new ResizeObserver(() => {
      timer && clearTimeout(timer)
      timer = window.setTimeout(() => this.engine.resize(), 15)
    })
    const dom = document.getElementById(domId)
    if (dom) this.resizeObserver.observe(dom)
  }

  /** 正交视口缩放系数(1 = 与视频画面同尺, 网格贴合人脸) */
  private orthoScale = 1

  /** 正交投影: 视口横向/纵向各覆盖一个画面归一化跨度, 与视频同尺映射 */
  private _applyOrtho() {
    const half = (SCALE / 2) * this.orthoScale
    this.camera.orthoLeft = -half
    this.camera.orthoRight = half
    this.camera.orthoTop = half
    this.camera.orthoBottom = -half
  }

  /** 正交模式滚轮缩放(radius 无视觉效果, 手动缩放视口) */
  private _onWheel = (e: WheelEvent) => {
    e.preventDefault()
    const factor = e.deltaY > 0 ? 1.1 : 1 / 1.1
    this.orthoScale = Math.min(3, Math.max(0.35, this.orthoScale * factor))
    this._applyOrtho()
  }

  /** 正交相机: 初始正对画面, 与视频同尺映射; 拖动旋转自由查看, 滚轮缩放视口 */
  private _cameraInit() {
    this.camera = new ArcRotateCamera('faceCam', -Math.PI / 2, Math.PI / 2, SCALE * 1.8, Vector3.Zero(), this.scene)
    this.camera.mode = Camera.ORTHOGRAPHIC_CAMERA
    this.camera.attachControl(this.canvas)
    this.camera.panningSensibility = 0 // 禁用平移, 避免把人脸拖丢
    this.camera.minZ = 0.1
    this.camera.maxZ = 200 // 收紧远裁剪面, 提升深度精度(减轻轮廓线与表面深度冲突)
    this._applyOrtho()
    this.canvas.addEventListener('wheel', this._onWheel, { passive: false })
  }

  private _lightInit() {
    // 半球环境光: 暖白天光 + 青瓷底色, 柔和过渡
    const hemi = new HemisphericLight('hemi', new Vector3(0, 1, 0), this.scene)
    hemi.diffuse = Color3.FromHexString('#f6faf7')
    hemi.groundColor = Color3.FromHexString('#b9cfc2')
    hemi.intensity = 0.9
    // 主光: 暖色点光从相机侧打光, 形成釉面高光
    const key = new PointLight('keyLight', new Vector3(0, SCALE * 0.6, -SCALE * 1.4), this.scene)
    key.intensity = 0.65
    key.diffuse = Color3.FromHexString('#fff2e2')
    // 补光: 左下冷青色弱光, 提亮背光面层次
    const fill = new PointLight('fillLight', new Vector3(-SCALE, -SCALE * 0.4, -SCALE * 0.8), this.scene)
    fill.intensity = 0.25
    fill.diffuse = Color3.FromHexString('#dcecd9')
  }

  dispose() {
    this.resizeObserver?.disconnect()
    this.canvas.removeEventListener('wheel', this._onWheel)
    this.engine.stopRenderLoop()
    this.scene.dispose()
    this.engine.dispose()
  }
}

export { FaceMeshScene }
