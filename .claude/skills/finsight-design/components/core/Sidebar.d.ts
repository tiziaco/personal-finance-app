export interface SidebarItem { id: string; label: string; icon: string; }
export interface SidebarProps { items: SidebarItem[]; active: string; onSelect?: (id: string) => void; }
/** @startingPoint section="Navigation" subtitle="96px icon rail with the Finsight mark" viewport="96x640" */
export declare function Sidebar(props: SidebarProps): JSX.Element;