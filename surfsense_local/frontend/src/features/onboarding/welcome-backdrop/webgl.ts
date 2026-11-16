import { VERTEX } from "./shaders"

export type Program = {
  program: WebGLProgram
  uniforms: Record<string, WebGLUniformLocation | null>
}

export type Target = {
  textures: WebGLTexture[]
  framebuffer: WebGLFramebuffer
  width: number
  height: number
}

function compile(gl: WebGL2RenderingContext, type: GLenum, source: string) {
  const shader = gl.createShader(type)
  if (!shader) return null
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return shader
  gl.deleteShader(shader)
  return null
}

/** A full-screen-triangle program with its uniforms looked up by name. */
export function link(
  gl: WebGL2RenderingContext,
  fragmentSource: string
): Program | null {
  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX)
  const fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource)
  const program = gl.createProgram()
  if (!vertex || !fragment) return null
  gl.attachShader(program, vertex)
  gl.attachShader(program, fragment)
  gl.linkProgram(program)
  gl.deleteShader(vertex)
  gl.deleteShader(fragment)
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program)
    return null
  }
  const uniforms: Program["uniforms"] = {}
  const count = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS) as number
  for (let i = 0; i < count; i++) {
    const info = gl.getActiveUniform(program, i)
    if (!info) continue
    const name = info.name.replace(/\[0\]$/, "")
    uniforms[name] = gl.getUniformLocation(program, name)
  }
  return { program, uniforms }
}

export function createTarget(
  gl: WebGL2RenderingContext,
  count: number
): Target {
  const textures = Array.from({ length: count }, () => {
    const texture = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, texture)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
    return texture
  })
  return { textures, framebuffer: gl.createFramebuffer(), width: 0, height: 0 }
}

export function sizeTarget(
  gl: WebGL2RenderingContext,
  target: Target,
  width: number,
  height: number
) {
  if (target.width === width && target.height === height) return
  target.width = width
  target.height = height
  gl.bindFramebuffer(gl.FRAMEBUFFER, target.framebuffer)
  target.textures.forEach((texture, i) => {
    gl.bindTexture(gl.TEXTURE_2D, texture)
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA8,
      width,
      height,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      null
    )
    gl.framebufferTexture2D(
      gl.FRAMEBUFFER,
      gl.COLOR_ATTACHMENT0 + i,
      gl.TEXTURE_2D,
      texture,
      0
    )
  })
  gl.bindFramebuffer(gl.FRAMEBUFFER, null)
}

export function deleteTarget(gl: WebGL2RenderingContext, target: Target) {
  target.textures.forEach((texture) => gl.deleteTexture(texture))
  gl.deleteFramebuffer(target.framebuffer)
}
