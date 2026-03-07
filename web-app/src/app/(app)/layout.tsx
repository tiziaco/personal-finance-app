import { AppSidebar } from "@/components/layout/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { HUB_NAV } from "@/lib/hub-nav";

export default function HubLayout({ children }: { children: React.ReactNode }) {
	return (
			<SidebarProvider>
				<AppSidebar items={HUB_NAV} variant="floating" />        {/* Navigation menu */}
				<SidebarInset className="flex flex-col overflow-hidden">
					<div className="flex-1 overflow-auto">
						<div className="px-2 py-2 min-w-0">
							{children}                           {/* Page content, <main> element */}
						</div>
					</div>
				</SidebarInset>
			</SidebarProvider>
	);
}

