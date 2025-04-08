"use client"

import {
  ExternalLink,
  Folder,
  MoreHorizontal,
  Share,
  Trash2,
  type LucideIcon,
} from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useRouter } from "next/navigation"

// Map of icon names to their components
const actionIconMap: Record<string, LucideIcon> = {
  ExternalLink,
  Folder,
  Share,
  Trash2,
  MoreHorizontal
}

interface ChatAction {
  name: string;
  icon: string;
  onClick: () => void;
}

export function NavProjects({
  projects,
}: {
  projects: {
    name: string
    url: string
    icon: LucideIcon
    id?: number
    search_space_id?: number
    actions?: ChatAction[]
  }[]
}) {
  const { isMobile } = useSidebar()
  const router = useRouter()
  
  const searchSpaceId = projects[0]?.search_space_id || ""

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Recent Chats</SidebarGroupLabel>
      <SidebarMenu>
        {projects.map((item, index) => (
          <SidebarMenuItem key={item.id ? `chat-${item.id}` : `chat-${item.name}-${index}`}>
            <SidebarMenuButton>
              <item.icon />
              <span>{item.name}</span>
            </SidebarMenuButton>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuAction showOnHover>
                  <MoreHorizontal />
                  <span className="sr-only">More</span>
                </SidebarMenuAction>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-48"
                side={isMobile ? "bottom" : "right"}
                align={isMobile ? "end" : "start"}
              >
                {item.actions ? (
                  // Use the actions provided by the item
                  item.actions.map((action, actionIndex) => {
                    const ActionIcon = actionIconMap[action.icon] || Folder;
                    return (
                      <DropdownMenuItem key={`${action.name}-${actionIndex}`} onClick={action.onClick}>
                        <ActionIcon className="text-muted-foreground" />
                        <span>{action.name}</span>
                      </DropdownMenuItem>
                    );
                  })
                ) : (
                  // Default actions if none provided
                  <>
                    <DropdownMenuItem>
                      <Folder className="text-muted-foreground" />
                      <span>View Chat</span>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem>
                      <Trash2 className="text-muted-foreground" />
                      <span>Delete Chat</span>
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        ))}
        <SidebarMenuItem>
          <SidebarMenuButton onClick={() => router.push(`/dashboard/${searchSpaceId}/chats`)}>
            <MoreHorizontal />
            <span>View All Chats</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  )
}
