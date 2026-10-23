/**
 * Lucide icon map for every SPA route in lib/nav.ts.
 * Callers: AppShell.tsx — navIcon(n.to). Size 18, stroke 1.75.
 * User: "Can we fix this? Also, the clutter in the dashboard…"
 */
import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  Award,
  BadgeDollarSign,
  BadgePercent,
  BookMarked,
  BookOpen,
  Boxes,
  Briefcase,
  Building,
  Building2,
  Calendar,
  CalendarClock,
  CircleDot,
  ClipboardCheck,
  ClipboardList,
  ClipboardPlus,
  CreditCard,
  Factory,
  FileDown,
  FileInput,
  FileMinus,
  FilePlus2,
  FileSearch,
  FileSpreadsheet,
  FileText,
  FolderTree,
  Globe2,
  Grid2x2,
  Hammer,
  HandCoins,
  Hash,
  Landmark,
  Layers,
  LayoutDashboard,
  ListOrdered,
  MapPin,
  Network,
  Package,
  PackageCheck,
  PackageOpen,
  Percent,
  Phone,
  Receipt,
  Scale,
  ScrollText,
  Settings,
  Shield,
  Ship,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Star,
  Store,
  Tags,
  Target,
  Truck,
  UserCog,
  Users,
  UsersRound,
  Wallet,
  Warehouse,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

const SZ = 18;
const SW = 1.75;

function ico(C: LucideIcon): ReactNode {
  return <C size={SZ} strokeWidth={SW} aria-hidden="true" />;
}

/** One glyph per sidebar section, used when the rail is icon-only. */
export function sectionIcon(key: string): ReactNode {
  switch (key) {
    case "nav.sales": return ico(ShoppingBag);
    case "nav.purchase": return ico(ShoppingCart);
    case "nav.stock": return ico(Warehouse);
    case "nav.accounting": return ico(Landmark);
    case "nav.masters": return ico(Tags);
    case "nav.compliance": return ico(Shield);
    case "nav.pos": return ico(Store);
    case "nav.fixedAssets": return ico(Boxes);
    case "nav.company": return ico(Building2);
    default: return ico(CircleDot);
  }
}

/** Lucide glyph for a rail route. Never returns null — keeps columns aligned. */
export function navIcon(to: string): ReactNode {
  switch (to) {
    case "/": return ico(LayoutDashboard);
    case "/customers": return ico(Users);
    case "/orders": return ico(ShoppingBag);
    case "/quotations": return ico(FileText);
    case "/delivery-notes": return ico(Truck);
    case "/invoices": return ico(Receipt);
    case "/payments": return ico(CreditCard);
    case "/receivables": return ico(ArrowDownLeft);
    case "/leads": return ico(Target);
    case "/suppliers": return ico(Building2);
    case "/supplier-quotations": return ico(FileInput);
    case "/purchase-orders": return ico(ShoppingCart);
    case "/purchase-receipts": return ico(PackageCheck);
    case "/incoming-invoices": return ico(FileDown);
    case "/purchase-invoices": return ico(FileMinus);
    case "/payables": return ico(ArrowUpRight);
    case "/stock-entries": return ico(PackageOpen);
    case "/stock-reconciliations": return ico(ClipboardCheck);
    case "/material-requests": return ico(ClipboardPlus);
    case "/serial-nos": return ico(Hash);
    case "/batches": return ico(Layers);
    case "/landed-cost-vouchers": return ico(Package);
    case "/boms": return ico(ClipboardList);
    case "/work-orders": return ico(Hammer);
    case "/pick-lists": return ico(ListOrdered);
    case "/journals": return ico(BookOpen);
    case "/bank-accounts": return ico(Landmark);
    case "/modes-of-payment": return ico(Wallet);
    case "/bank-reconciliation": return ico(ArrowLeftRight);
    case "/fiscal-years": return ico(Calendar);
    case "/accounts": return ico(BookMarked);
    case "/currency-exchanges": return ico(Globe2);
    case "/reports": return ico(FileSearch);
    case "/catalogue/items": return ico(Tags);
    case "/catalogue/item-groups": return ico(Grid2x2);
    case "/catalogue/brands": return ico(Sparkles);
    case "/catalogue/uoms": return ico(Scale);
    case "/warehouses": return ico(Warehouse);
    case "/price-lists": return ico(BadgeDollarSign);
    case "/payment-terms-templates": return ico(CalendarClock);
    case "/tax-templates": return ico(FilePlus2);
    case "/tax-categories": return ico(FileSpreadsheet);
    case "/item-tax-templates": return ico(Percent);
    case "/pricing-rules": return ico(BadgePercent);
    case "/customer-groups": return ico(UsersRound);
    case "/supplier-groups": return ico(Building);
    case "/territories": return ico(MapPin);
    case "/addresses": return ico(MapPin);
    case "/contacts": return ico(Phone);
    case "/terms-and-conditions": return ico(ScrollText);
    case "/vat-201": return ico(BadgePercent);
    case "/ct-filings": return ico(Shield);
    case "/esr": return ico(FileSearch);
    case "/ubo": return ico(UserCog);
    case "/late-filings": return ico(AlertTriangle);
    case "/e-invoice-log": return ico(Receipt);
    case "/tax-settings": return ico(Settings);
    case "/uae-related-parties": return ico(Network);
    case "/uae-vat-groups": return ico(UsersRound);
    case "/uae-bad-debt-relief": return ico(HandCoins);
    case "/uae-customs-declarations": return ico(Ship);
    case "/uae-capital-goods-adjustments": return ico(Factory);
    case "/pos":
    case "/pos-invoices": return ico(Store);
    case "/pos-profiles": return ico(Briefcase);
    case "/loyalty-programs": return ico(Star);
    case "/loyalty-point-entries": return ico(Award);
    case "/assets": return ico(Boxes);
    case "/asset-categories": return ico(FolderTree);
    case "/company": return ico(Settings);
    case "/team": return ico(Users);
    default: return ico(CircleDot);
  }
}
