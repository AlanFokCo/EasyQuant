/**
 * UI Components barrel export.
 *
 * All shadcn/ui-style components are available from this single import:
 *   import { Button, Input, Card, Dialog, Table } from "@/components/ui";
 */
export { Button, buttonVariants, type ButtonProps } from "./button";
export { Input, type InputProps } from "./input";
export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "./card";
export {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogClose,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "./dialog";
export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
} from "./table";
