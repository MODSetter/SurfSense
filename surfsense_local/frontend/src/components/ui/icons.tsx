import * as React from "react"
import {
  AlertCircleIcon,
  ArrowDownIcon as ArrowDownIconData,
  ArrowLeftIcon as ArrowLeftIconData,
  ArrowUp02Icon as ArrowUp02IconData,
  BotIcon as BotIconData,
  BrainCircuitIcon as BrainCircuitIconData,
  CheckIcon as CheckIconData,
  CheckmarkCircle02Icon,
  ChevronDownIcon as ChevronDownIconData,
  ChevronRightIcon as ChevronRightIconData,
  Copy01Icon,
  Delete02Icon,
  DownloadIcon as DownloadIconData,
  EllipsisIcon as EllipsisIconData,
  FileAddIcon,
  FileIcon as FileIconData,
  FileTextIcon as FileTextIconData,
  KeyRoundIcon as KeyRoundIconData,
  LayoutGridIcon as LayoutGridIconData,
  Loading03Icon,
  MessageSquareIcon as MessageSquareIconData,
  NotebookTextIcon as NotebookTextIconData,
  PencilIcon as PencilIconData,
  PlusIcon as PlusIconData,
  RefreshCwIcon as RefreshCwIconData,
  ServerOffIcon as ServerOffIconData,
  Settings02Icon,
  SparklesIcon as SparklesIconData,
  StopCircleIcon,
  XIcon as XIconData,
} from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

type IconData = React.ComponentProps<typeof HugeiconsIcon>["icon"]
type IconProps = Omit<React.ComponentProps<typeof HugeiconsIcon>, "icon">

function createIcon(icon: IconData) {
  return React.forwardRef<SVGSVGElement, IconProps>(function Icon(props, ref) {
    return <HugeiconsIcon ref={ref} icon={icon} strokeWidth={2} {...props} />
  })
}

export const ArrowDownIcon = createIcon(ArrowDownIconData)
export const ArrowLeftIcon = createIcon(ArrowLeftIconData)
export const ArrowUp02Icon = createIcon(ArrowUp02IconData)
export const BotIcon = createIcon(BotIconData)
export const BrainCircuitIcon = createIcon(BrainCircuitIconData)
export const CheckCircle2Icon = createIcon(CheckmarkCircle02Icon)
export const CheckIcon = createIcon(CheckIconData)
export const ChevronDownIcon = createIcon(ChevronDownIconData)
export const ChevronRightIcon = createIcon(ChevronRightIconData)
export const CircleAlertIcon = createIcon(AlertCircleIcon)
export const CircleStopIcon = createIcon(StopCircleIcon)
export const CopyIcon = createIcon(Copy01Icon)
export const DownloadIcon = createIcon(DownloadIconData)
export const EllipsisIcon = createIcon(EllipsisIconData)
export const FileIcon = createIcon(FileIconData)
export const FilePlus2Icon = createIcon(FileAddIcon)
export const FileTextIcon = createIcon(FileTextIconData)
export const KeyRoundIcon = createIcon(KeyRoundIconData)
export const LayoutGridIcon = createIcon(LayoutGridIconData)
export const Loader2Icon = createIcon(Loading03Icon)
export const MessageSquareIcon = createIcon(MessageSquareIconData)
export const NotebookTextIcon = createIcon(NotebookTextIconData)
export const PencilIcon = createIcon(PencilIconData)
export const PlusIcon = createIcon(PlusIconData)
export const RefreshCwIcon = createIcon(RefreshCwIconData)
export const ServerOffIcon = createIcon(ServerOffIconData)
export const Settings2Icon = createIcon(Settings02Icon)
export const SparklesIcon = createIcon(SparklesIconData)
export const Trash2Icon = createIcon(Delete02Icon)
export const XIcon = createIcon(XIconData)
