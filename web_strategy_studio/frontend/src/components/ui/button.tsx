/**
 * Button — shadcn/ui-style button with variants and sizes.
 *
 * Variants: default | secondary | ghost | danger | outline
 * Sizes: sm | md | lg | icon
 */
import { forwardRef } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2",
    "text-sm font-medium whitespace-nowrap",
    "rounded-md transition-all",
    "disabled:pointer-events-none disabled:opacity-50",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
  ].join(" "),
  {
    variants: {
      variant: {
        default:
          "bg-primary text-white hover:bg-primary-hover active:scale-[0.98] shadow-sm",
        secondary:
          "bg-surface border border-border hover:bg-surface-raised active:scale-[0.98]",
        ghost:
          "hover:bg-surface-raised active:scale-[0.98]",
        outline:
          "border border-border bg-transparent hover:bg-surface-raised active:scale-[0.98]",
        danger:
          "bg-danger text-white hover:opacity-90 active:scale-[0.98] shadow-sm",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4 text-sm",
        lg: "h-11 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** When true, renders children inside a Slot (Radix asChild pattern). */
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { buttonVariants };
