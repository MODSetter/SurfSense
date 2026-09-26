// The commands that install what a stage lacks, with this machine's package
// manager. A tool with no package there is named in the message, not here.

const INSTALL = {
  apt: (packages) => [`sudo apt install ${packages.join(" ")}`],
  dnf: (packages) => [`sudo dnf install ${packages.join(" ")}`],
  pacman: (packages) => [`sudo pacman -S --needed ${packages.join(" ")}`],
  brew: (packages) => [`brew install ${packages.join(" ")}`],
  // winget takes one package per call.
  winget: (packages) => packages.map((id) => `winget install ${id}`),
}

export function installCommands(missing, manager) {
  const commands = missing.flatMap((tool) => tool.command ?? [])
  const packages = [...new Set(missing.flatMap((tool) => tool.packages?.[manager] ?? []))]
  if (packages.length) commands.push(...INSTALL[manager](packages))
  return commands
}
