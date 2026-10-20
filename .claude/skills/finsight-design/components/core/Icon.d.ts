export interface IconProps {
  /** Lucide icon name, e.g. "layout-dashboard", "wallet", "arrow-down-left". */
  name: string;
  size?: number;
  color?: string;
}
export declare function Icon(props: IconProps): JSX.Element;