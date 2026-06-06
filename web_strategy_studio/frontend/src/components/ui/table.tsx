/**
 * Table — shadcn/ui-style table components.
 */
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

/* ── Table ───────────────────────────────────────────────── */

export const Table = forwardRef<HTMLTableElement, React.HTMLAttributes<HTMLTableElement>>(
  ({ className, ...props }, ref) => (
    <div className="relative w-full overflow-auto">
      <table
        ref={ref}
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
);
Table.displayName = "Table";

/* ── TableHeader ─────────────────────────────────────────── */

export const TableHeader = forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
  )
);
TableHeader.displayName = "TableHeader";

/* ── TableBody ───────────────────────────────────────────── */

export const TableBody = forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tbody ref={ref} className={cn("[&_tr:last-child]:border-0", className)} {...props} />
  )
);
TableBody.displayName = "TableBody";

/* ── TableFooter ─────────────────────────────────────────── */

export const TableFooter = forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tfoot
      ref={ref}
      className={cn("border-t bg-surface-raised font-medium [&>tr]:last:border-b-0", className)}
      {...props}
    />
  )
);
TableFooter.displayName = "TableFooter";

/* ── TableRow ────────────────────────────────────────────── */

export const TableRow = forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn(
        "border-b border-border transition-colors hover:bg-surface-raised data-[state=selected]:bg-surface-raised",
        className
      )}
      {...props}
    />
  )
);
TableRow.displayName = "TableRow";

/* ── TableHead ───────────────────────────────────────────── */

export const TableHead = forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <th
      ref={ref}
      className={cn(
        [
          "h-10 px-3 text-left align-middle",
          "font-medium text-text-secondary",
          "[&:has([role=checkbox])]:pr-0",
        ].join(" "),
        className
      )}
      {...props}
    />
  )
);
TableHead.displayName = "TableHead";

/* ── TableCell ───────────────────────────────────────────── */

export const TableCell = forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <td
      ref={ref}
      className={cn("p-3 align-middle [&:has([role=checkbox])]:pr-0", className)}
      {...props}
    />
  )
);
TableCell.displayName = "TableCell";

/* ── TableCaption ────────────────────────────────────────── */

export const TableCaption = forwardRef<HTMLTableCaptionElement, React.HTMLAttributes<HTMLTableCaptionElement>>(
  ({ className, ...props }, ref) => (
    <caption
      ref={ref}
      className={cn("mt-4 text-sm text-text-secondary", className)}
      {...props}
    />
  )
);
TableCaption.displayName = "TableCaption";
