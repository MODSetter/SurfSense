import * as React from "react"
import {
  Alert02Icon as Alert02IconData,
  AlertCircleIcon,
  AiSearchLinesIcon as AiSearchLinesIconData,
  ArrowDownIcon as ArrowDownIconData,
  ArrowExpand01Icon as ArrowExpand01IconData,
  ArrowLeftIcon as ArrowLeftIconData,
  ArrowRightIcon as ArrowRightIconData,
  ArrowUp02Icon as ArrowUp02IconData,
  BotIcon as BotIconData,
  BrainCircuitIcon as BrainCircuitIconData,
  CancelCircleHalfDotIcon as CancelCircleHalfDotIconData,
  Cards01Icon as Cards01IconData,
  ChartHistogramIcon as ChartHistogramIconData,
  Chat01Icon as Chat01IconData,
  CheckIcon as CheckIconData,
  CheckmarkCircle02Icon,
  ChevronDownIcon as ChevronDownIconData,
  ChevronRightIcon as ChevronRightIconData,
  ComputerEthernetIcon as ComputerEthernetIconData,
  Copy01Icon,
  CpuIcon as CpuIconData,
  CursorRemoveSelection02Icon as CursorRemoveSelection02IconData,
  Delete02Icon,
  Download01Icon as Download01IconData,
  DownloadCircle02Icon as DownloadCircle02IconData,
  DownloadIcon as DownloadIconData,
  DotIcon as DotIconData,
  EllipsisIcon as EllipsisIconData,
  File02Icon as File02IconData,
  FileAddIcon,
  FileIcon as FileIconData,
  FileTextIcon as FileTextIconData,
  FilterIcon as FilterIconData,
  FolderOpenIcon as FolderOpenIconData,
  Image01Icon as Image01IconData,
  InformationCircleIcon as InformationCircleIconData,
  LayoutGridIcon as LayoutGridIconData,
  LicenseIcon as LicenseIconData,
  LightbulbIcon as LightbulbIconData,
  Loading03Icon,
  Moon02Icon as Moon02IconData,
  NetworkIcon as NetworkIconData,
  NotebookTextIcon as NotebookTextIconData,
  PencilEdit02Icon as PencilEdit02IconData,
  Pdf01Icon as Pdf01IconData,
  PencilIcon as PencilIconData,
  PlusIcon as PlusIconData,
  PodcastIcon as PodcastIconData,
  Presentation02Icon as Presentation02IconData,
  Quiz02Icon as Quiz02IconData,
  RefreshCwIcon as RefreshCwIconData,
  Search01Icon,
  ServerIcon as ServerIconData,
  ServerOffIcon as ServerOffIconData,
  SidebarRight01Icon as SidebarRight01IconData,
  Settings02Icon,
  ShuffleIcon as ShuffleIconData,
  SparklesIcon as SparklesIconData,
  SquareDashedMousePointerIcon as SquareDashedMousePointerIconData,
  StopCircleIcon,
  Sun03Icon as Sun03IconData,
  UnplugIcon as UnplugIconData,
  Upload01Icon as Upload01IconData,
  ComputerIcon as ComputerIconData,
  ViewIcon as ViewIconData,
  WebDesign01Icon as WebDesign01IconData,
  XIcon as XIconData,
  Xls01Icon as Xls01IconData,
  ZoomInIcon as ZoomInIconData,
  ZoomOutIcon as ZoomOutIconData,
} from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"

type IconData = React.ComponentProps<typeof HugeiconsIcon>["icon"]
type IconProps = Omit<
  React.ComponentProps<typeof HugeiconsIcon>,
  "icon" | "strokeWidth"
> & {
  strokeWidth?: React.SVGProps<SVGSVGElement>["strokeWidth"]
}

function createIcon(icon: IconData, defaultClassName?: string) {
  return React.forwardRef<SVGSVGElement, IconProps>(function Icon(
    { strokeWidth = 2, className, ...props },
    ref
  ) {
    const width =
      typeof strokeWidth === "number"
        ? strokeWidth
        : Number.parseFloat(strokeWidth) || 2
    return (
      <HugeiconsIcon
        ref={ref}
        icon={icon}
        strokeWidth={width}
        className={cn(defaultClassName, className)}
        {...props}
      />
    )
  })
}

export const Alert02Icon = createIcon(Alert02IconData)
export const AiSearchLinesIcon = createIcon(AiSearchLinesIconData)
export const ArrowDownIcon = createIcon(ArrowDownIconData)
export const ArrowExpand01Icon = createIcon(ArrowExpand01IconData)
export const ArrowLeftIcon = createIcon(ArrowLeftIconData)
export const ArrowRightIcon = createIcon(ArrowRightIconData)
export const ArrowUp02Icon = createIcon(ArrowUp02IconData)
export const BotIcon = createIcon(BotIconData)
export const BrainCircuitIcon = createIcon(BrainCircuitIconData)
export const CancelCircleHalfDotIcon = createIcon(CancelCircleHalfDotIconData)
export const Cards01Icon = createIcon(Cards01IconData)
export const ChartHistogramIcon = createIcon(ChartHistogramIconData)
export const Chat01Icon = createIcon(Chat01IconData)
export const CheckCircle2Icon = createIcon(CheckmarkCircle02Icon)
export const CheckIcon = createIcon(CheckIconData)
export const ChevronDownIcon = createIcon(ChevronDownIconData)
export const ChevronRightIcon = createIcon(ChevronRightIconData)
export const ComputerEthernetIcon = createIcon(ComputerEthernetIconData)
export const CircleAlertIcon = createIcon(AlertCircleIcon)
export const CircleStopIcon = createIcon(StopCircleIcon)
export const CopyIcon = createIcon(Copy01Icon)
export const CpuIcon = createIcon(CpuIconData)
export const CursorRemoveSelection02Icon = createIcon(
  CursorRemoveSelection02IconData
)
export const Download01Icon = createIcon(Download01IconData)
export const DownloadIcon = createIcon(DownloadIconData)
export const DotIcon = createIcon(DotIconData)
export const EllipsisIcon = createIcon(EllipsisIconData)
export const File02Icon = createIcon(File02IconData)
export const FileIcon = createIcon(FileIconData)
export const FilePlus2Icon = createIcon(FileAddIcon)
export const FileTextIcon = createIcon(FileTextIconData)
export const FilterIcon = createIcon(FilterIconData)
export const FolderOpenIcon = createIcon(FolderOpenIconData)
export const Image01Icon = createIcon(Image01IconData)
export const InformationCircleIcon = createIcon(InformationCircleIconData)
export const LayoutGridIcon = createIcon(LayoutGridIconData)
export const LicenseIcon = createIcon(LicenseIconData)
export const LightbulbIcon = createIcon(LightbulbIconData)
export const Loader2Icon = createIcon(Loading03Icon)
export const MoonIcon = createIcon(Moon02IconData)
export const NetworkIcon = createIcon(NetworkIconData, "rotate-90")
export const NotebookTextIcon = createIcon(NotebookTextIconData)
export const PencilEdit02Icon = createIcon(PencilEdit02IconData)
export const Pdf01Icon = createIcon(Pdf01IconData)
export const PencilIcon = createIcon(PencilIconData)
export const PlusIcon = createIcon(PlusIconData)
export const PodcastIcon = createIcon(PodcastIconData)
export const Presentation02Icon = createIcon(Presentation02IconData)
export const Quiz02Icon = createIcon(Quiz02IconData)
export const RefreshCwIcon = createIcon(RefreshCwIconData)
export const SearchIcon = createIcon(Search01Icon)
export const ServerIcon = createIcon(ServerIconData)
export const ServerOffIcon = createIcon(ServerOffIconData)
export const DownloadCircle02Icon = createIcon(DownloadCircle02IconData)
export const SidebarRightIcon = createIcon(SidebarRight01IconData)
export const Settings2Icon = createIcon(Settings02Icon)
export const ShuffleIcon = createIcon(ShuffleIconData)
export const SparklesIcon = createIcon(SparklesIconData)
export const SunIcon = createIcon(Sun03IconData)
export const UnplugIcon = createIcon(UnplugIconData)
export const Upload01Icon = createIcon(Upload01IconData)
export const ComputerIcon = createIcon(ComputerIconData)
export const SquareDashedMousePointerIcon = createIcon(
  SquareDashedMousePointerIconData
)
export const Trash2Icon = createIcon(Delete02Icon)
export const ViewIcon = createIcon(ViewIconData)
export const WebDesign01Icon = createIcon(WebDesign01IconData)
export const XIcon = createIcon(XIconData)
export const Xls01Icon = createIcon(Xls01IconData)
export const ZoomInIcon = createIcon(ZoomInIconData)
export const ZoomOutIcon = createIcon(ZoomOutIconData)
