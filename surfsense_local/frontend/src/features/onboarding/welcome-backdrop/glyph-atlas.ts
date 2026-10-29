export const ATLAS_CELL_W = 60
export const ATLAS_CELL_H = 100
const ATLAS_COLUMNS = 16
const FONT_SCALE = 0.78

export type GlyphAtlas = {
  texture: WebGLTexture
  count: number
  grid: [number, number]
}

/** The characters drawn once to a mipmapped texture, dimmest first. */
export function buildAtlas(
  gl: WebGL2RenderingContext,
  characters: string,
  fontFamily: string
): GlyphAtlas {
  const list = [
    ...new Set(
      [...characters].filter((char) => char !== "\n" && char !== "\r")
    ),
  ]
  if (!list.length) list.push(" ")
  const columns = Math.min(ATLAS_COLUMNS, list.length)
  const rows = Math.ceil(list.length / columns)
  const canvas = document.createElement("canvas")
  canvas.width = ATLAS_CELL_W * columns
  canvas.height = ATLAS_CELL_H * rows
  const context = canvas.getContext("2d")
  if (context) {
    context.font = `300 ${Math.round(ATLAS_CELL_H * FONT_SCALE)}px ${fontFamily}`
    context.textAlign = "center"
    context.textBaseline = "middle"
    context.fillStyle = "#fff"
    list.forEach((char, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      context.fillText(
        char,
        column * ATLAS_CELL_W + ATLAS_CELL_W / 2,
        row * ATLAS_CELL_H + ATLAS_CELL_H / 2 + 3
      )
    })
  }
  const texture = gl.createTexture()
  gl.bindTexture(gl.TEXTURE_2D, texture)
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false)
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, canvas)
  gl.generateMipmap(gl.TEXTURE_2D)
  gl.texParameteri(
    gl.TEXTURE_2D,
    gl.TEXTURE_MIN_FILTER,
    gl.LINEAR_MIPMAP_LINEAR
  )
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
  return { texture, count: list.length, grid: [columns, rows] }
}
