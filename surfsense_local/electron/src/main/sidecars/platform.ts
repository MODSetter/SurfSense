export const isWindows = process.platform === "win32"

// onedir binaries and the llama.cpp archive name the executable after the tool;
// Windows adds .exe.
export const exe = (name: string): string => (isWindows ? `${name}.exe` : name)
