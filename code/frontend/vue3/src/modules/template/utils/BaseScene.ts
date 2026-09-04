import {
  Scene,
  Engine,
  FreeCamera,
  Vector3,
  HemisphericLight,
  PointLight,
  MeshBuilder,
  Color3,
  Color4,
  StandardMaterial,
  Texture,
  ArcRotateCamera,
  Camera,
} from 'babylonjs'
// import earth_0 from '@/assets/img/earth_0.png'
/**
 * 基础场景
 */
class BaseScene {
  canvas: HTMLCanvasElement
  engine: Engine
  camera: Camera | undefined
  scene: Scene | undefined
  /**
   *
   * @param dom canvas id
   */
  constructor(dom: string) {
    this.canvas = document.getElementById(dom) as HTMLCanvasElement
    // Load the 3D engine // 初始化 BABYLON 3D engine
    this.engine = new Engine(this.canvas, true, {
      preserveDrawingBuffer: true,
      stencil: true,
    })
    //
    // Create a basic BJS Scene object 创建一个场景scene
    this.scene = new Scene(this.engine)
    this.scene.clearColor = new Color4(0, 0, 0, 0) // 背景透明
    // 循环渲染
    this.engine.runRenderLoop(() => {
      this.scene!.render()
    })
    // 场景内渲染
    this._init()
  }

  /**
   *
   */
  private _init() {
    this._cameraInit()
    this._lightInit()
    this._meshInit()
  }

  private _cameraInit() {
    // 透视相机
    // fov	相机视锥体竖直方向视野角度
    // aspect	相机视锥体水平方向和竖直方向长度比，一般设置为Canvas画布宽高比width / height
    // near	相机视锥体近裁截面相对相机距离
    // far	相机视锥体远裁截面相对相机距离，far-near构成了视锥体高度方向
    const fov = 45
    const aspect = this.canvas.width / this.canvas.height
    const near = 0.1
    const far = 1000

    // 创建透视相机
    this.camera = new FreeCamera('camera1', new Vector3(0, 0, -100), this.scene)
    // // 设置相机目标点
    // this.camera.setTarget(Vector3.Zero())
    // // 附加相机到画布
    // this.camera.attachControl(this.canvas, true)
  }

  private _lightInit() {
    // Create a basic light, aiming 0, 1, 0 - meaning, to the sky 添加一组灯光到场景
    const light = new HemisphericLight('light1', new Vector3(0, 1, 0), this.scene)
    // const light2 = newPointLight('light2', newVector3(0, 1, -1), this.scene)
  }

  private pointMeshes: any[] = []

  private _meshInit() {
    // 初始化时不创建点，等待外部调用 initPoints 方法
  }

  /**
   * 初始化点（首次创建）
   * @param faces 三维数组，每个元素包含三个值 [x, y, z]
   */
  initPoints(faces: number[][]) {
    // 清除旧的点
    this.pointMeshes.forEach(mesh => {
      mesh.dispose()
    })
    this.pointMeshes = []

    // 为每个点创建一个小球体作为标记
    faces.forEach((face, index) => {
      // 将 0-1 的值映射到 -20 到 20 的范围
      const x = (face[0] - 0.5) * 40
      const y = (face[1] - 0.5) * 40
      const z = (face[2] - 0.5) * 40

      const pointMesh = MeshBuilder.CreateSphere(`point_${index}`, { diameter: 2 }, this.scene)
      pointMesh.position = new Vector3(x, y, z)

      // 创建材质，颜色根据 face 值变化
      const material = new StandardMaterial(`material_${index}`, this.scene)
      material.diffuseColor = new Color3(face[0], face[1], face[2])
      material.specularColor = new Color3(0.5, 0.5, 0.5)

      pointMesh.material = material
      this.pointMeshes.push(pointMesh)
    })
  }

  /**
   * 更新点位置（不重新创建，只更新位置和颜色）
   * @param faces 三维数组，每个元素包含三个值 [x, y, z]
   */
  updatePoints(faces: number[][]) {
    // 如果点数不匹配，需要重新初始化
    if (this.pointMeshes.length !== faces.length) {
      this.initPoints(faces)
      return
    }

    // 只更新位置和颜色
    faces.forEach((face, index) => {
      const mesh = this.pointMeshes[index]
      if (mesh) {
        // 更新位置
        mesh.position.x = (face[0] - 0.5) * 40
        mesh.position.y = (face[1] - 0.5) * 40
        mesh.position.z = (face[2] - 0.5) * 40

        // 更新材质颜色
        if (mesh.material) {
          mesh.material.diffuseColor = new Color3(face[0], face[1], face[2])
        }
      }
    })
  }

  /**
   * 初始化监听
   */
  observeInit(dom: string) {
    // the canvas/window resize event handler 监听浏览器改变大小的事件，通过调用engine.resize()来自适应窗口大小
    // window.addEventListener('resize', function () {
    //   engine.resize()
    // })

    // 监听元素变化
    let tempSetTime: number | undefined = undefined
    const resizeObserver = new ResizeObserver(() => {
      tempSetTime && clearTimeout(tempSetTime)
      tempSetTime = setTimeout(() => {
        this.engine.resize()
      }, 15)
    })
    resizeObserver.observe(document.getElementById(dom) as HTMLElement)
    //// resizeObserver.unobserve(canvasP)// 取消监听元素
  }

  dispose() {}
}

export { BaseScene }
