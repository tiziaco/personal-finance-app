import {
  ArrowDownLeftIcon,
  BanknoteIcon,
  BikeIcon,
  CarIcon,
  CoinsIcon,
  GraduationCapIcon,
  HeartHandshakeIcon,
  HouseIcon,
  LandmarkIcon,
  PiggyBankIcon,
  PillIcon,
  PlaneIcon,
  ShapesIcon,
  ShieldCheckIcon,
  ShoppingBagIcon,
  ShoppingCartIcon,
  SmartphoneIcon,
  TagIcon,
  TicketIcon,
  UsersIcon,
  UtensilsIcon,
  type LucideIcon,
} from "lucide-react"
import { createElement } from "react"
import { cn } from "@app/core/lib/utils"

/**
 * One icon per category slug. The list lives on the server (`CATEGORIES`);
 * a slug added there needs a row here, and until it has one it shows Tag.
 */
export const CATEGORY_ICONS: Record<string, LucideIcon> = {
  income: ArrowDownLeftIcon,
  salary: BanknoteIcon,
  transportation: CarIcon,
  household_utilities: HouseIcon,
  tax_fines: LandmarkIcon,
  food_groceries: ShoppingCartIcon,
  food_delivery: BikeIcon,
  bars_restaurants: UtensilsIcon,
  atm: CoinsIcon,
  insurances: ShieldCheckIcon,
  shopping: ShoppingBagIcon,
  education: GraduationCapIcon,
  family_friends: UsersIcon,
  donations_charity: HeartHandshakeIcon,
  healthcare_drug_stores: PillIcon,
  leisure_entertainment: TicketIcon,
  media_electronics: SmartphoneIcon,
  savings_investments: PiggyBankIcon,
  travel_holidays: PlaneIcon,
  miscellaneous: ShapesIcon,
}

export const categoryIcon = (slug: string): LucideIcon =>
  CATEGORY_ICONS[slug] ?? TagIcon

/** The design system's neutral tile that leads a transaction row. */
export function CategoryTile({
  slug,
  size = "md",
}: {
  slug: string
  size?: "md" | "sm"
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center rounded-lg bg-muted text-(--text-secondary)",
        size === "md" ? "size-9 [&_svg]:size-4.5" : "size-8 [&_svg]:size-4",
      )}
    >
      {createElement(categoryIcon(slug))}
    </span>
  )
}

/** The bare icon, inline before a category's name. */
export function CategoryGlyph({ slug }: { slug: string }) {
  // createElement, not <Icon />: the icon is looked up, not created, per render.
  return createElement(categoryIcon(slug), {
    "aria-hidden": true,
    className: "size-4 shrink-0",
  })
}
