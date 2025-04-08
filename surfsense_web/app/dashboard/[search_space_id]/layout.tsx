// Server component
import React, { use } from 'react'
import { DashboardClientLayout } from './client-layout'

export default function DashboardLayout({ 
  params, 
  children 
}: { 
  params: Promise<{ search_space_id: string }>, 
  children: React.ReactNode 
}) {
  // Use React.use to unwrap the params Promise
  const { search_space_id } = use(params);

  // TODO: Get search space name from our FastAPI backend
  const customNavSecondary = [
    {
      title: `All Search Spaces`,
      url: `#`,
      icon: "Info",
    },
    {
      title: `All Search Spaces`,
      url: "/dashboard",
      icon: "Undo2",
    },
  ]

  const customNavMain = [
    {
      title: "Researcher",
      url: `/dashboard/${search_space_id}/researcher`,
      icon: "SquareTerminal",
      isActive: true,
      items: [],
    },

    {
      title: "Documents",
      url: "#",
      icon: "FileStack",
      items: [
        {
          title: "Upload Documents",
          url: `/dashboard/${search_space_id}/documents/upload`,
        },
        {
          title: "Add Webpages",
          url: `/dashboard/${search_space_id}/documents/webpage`,
        },
        {
          title: "Manage Documents",
          url: `/dashboard/${search_space_id}/documents`,
        },
      ],
    },
    {
      title: "Connectors",
      url: `#`,
      icon: "Cable",
      items: [
        {
          title: "Add Connector",
          url: `/dashboard/${search_space_id}/connectors/add`,
        },
        {
          title: "Manage Connectors",
          url: `/dashboard/${search_space_id}/connectors`,
        },
      ],
    },
    // TODO: Add research synthesizer's
    // {
    //   title: "Research Synthesizer's",
    //   url: `#`,
    //   icon: "SquareLibrary",
    //   items: [
    //     {
    //       title: "Podcast Creator",
    //       url: `/dashboard/${search_space_id}/synthesizer/podcast`,
    //     },
    //     {
    //       title: "Presentation Creator",
    //       url: `/dashboard/${search_space_id}/synthesizer/presentation`,
    //     },
    //   ],
    // },
  ]

  return (
    <DashboardClientLayout
      searchSpaceId={search_space_id}
      navSecondary={customNavSecondary}
      navMain={customNavMain}
    >
      {children}
    </DashboardClientLayout>
  )
}