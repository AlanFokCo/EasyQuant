# 前端 UI/UX 全面重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全面重构前端UI/UX，实现专业级量化平台界面，暗色主题，响应式布局，流畅动效。

**Architecture:** 升级至React 19 + Vite 6 + shadcn/ui + Tailwind 4 + Framer Motion，统一设计系统。

**Tech Stack:** React 19, Vite 6, TypeScript 5.6, shadcn/ui, Tailwind CSS 4, Framer Motion, Radix UI

---

## 文件结构

```
frontend/src/components/ui/          → shadcn/ui 组件库
frontend/src/styles/theme.css      → 主题配置
frontend/src/styles/design-tokens.ts → 设计令牌
frontend/src/components/Layout.tsx   → 全局布局
frontend/src/components/Sidebar.tsx  → 侧边栏
frontend/src/components/Header.tsx   → 顶部导航
frontend/src/components/StatusBar.tsx → 状态栏
frontend/src/hooks/useTheme.ts     → 主题Hook
frontend/src/hooks/useKeyboardShortcuts.ts → 快捷键
```

---

### Task 1: 初始化前端项目

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`

- [ ] **Step 1: 创建package.json**

```json
{
  "name": "eq-studio-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^5.0.0",
    "framer-motion": "^12.0.0",
    "lucide-react": "^0.460.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^3.0.0",
    "class-variance-authority": "^0.7.0",
    "@radix-ui/react-dialog": "^1.0.0",
    "@radix-ui/react-dropdown-menu": "^2.0.0",
    "@radix-ui/react-tabs": "^1.0.0",
    "@radix-ui/react-tooltip": "^1.0.0",
    "@radix-ui/react-toast": "^1.0.0",
    "@radix-ui/react-select": "^2.0.0",
    "@radix-ui/react-checkbox": "^1.0.0",
    "@radix-ui/react-radio-group": "^1.0.0",
    "@radix-ui/react-slider": "^1.0.0",
    "@radix-ui/react-switch": "^1.0.0",
    "@radix-ui/react-avatar": "^1.0.0",
    "@radix-ui/react-separator": "^1.0.0",
    "@radix-ui/react-scroll-area": "^1.0.0",
    "@radix-ui/react-collapsible": "^1.0.0",
    "@radix-ui/react-context-menu": "^2.0.0",
    "@radix-ui/react-hover-card": "^1.0.0",
    "@radix-ui/react-menubar": "^1.0.0",
    "@radix-ui/react-navigation-menu": "^1.0.0",
    "@radix-ui/react-popover": "^1.0.0",
    "@radix-ui/react-progress": "^1.0.0",
    "@radix-ui/react-slider": "^1.0.0",
    "@radix-ui/react-slot": "^1.0.0",
    "@radix-ui/react-toggle": "^1.0.0",
    "@radix-ui/react-toggle-group": "^1.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "tailwindcss": "^4.0.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^9.0.0",
    "@eslint/js": "^9.0.0",
    "typescript-eslint": "^8.0.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-react-refresh": "^0.4.0",
    "@tailwindcss/vite": "^4.0.0"
  }
}
```

- [ ] **Step 2: 创建Tailwind配置**

```typescript
// frontend/tailwind.config.ts
import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0f1115',
        surface: '#181a20',
        'surface-raised': '#1e2028',
        border: '#2a2d35',
        primary: {
          DEFAULT: '#3b82f6',
          hover: '#2563eb',
        },
        success: '#22c55e',
        warning: '#eab308',
        danger: '#ef4444',
        info: '#06b6d4',
        text: {
          primary: '#f1f5f9',
          secondary: '#94a3b8',
          muted: '#64748b',
          inverse: '#0f1115',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'SF Mono', 'Consolas', 'monospace'],
      },
      fontSize: {
        display: ['2rem', { lineHeight: '1.25' }],
        'heading-1': ['1.5rem', { lineHeight: '1.25' }],
        'heading-2': ['1.25rem', { lineHeight: '1.25' }],
        'heading-3': ['1rem', { lineHeight: '1.5' }],
        body: ['0.875rem', { lineHeight: '1.5' }],
        'body-sm': ['0.75rem', { lineHeight: '1.5' }],
        caption: ['0.6875rem', { lineHeight: '1.5' }],
      },
      spacing: {
        '0.5': '2px',
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '5': '20px',
        '6': '24px',
        '8': '32px',
        '10': '40px',
        '12': '48px',
        '16': '64px',
      },
      borderRadius: {
        DEFAULT: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      transitionTimingFunction: {
        'ease-out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'scale-in': {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        'pulse-slow': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
        'fade-in-up': 'fade-in-up 0.2s ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out-expo',
        'scale-in': 'scale-in 0.2s ease-out-expo',
        'pulse-slow': 'pulse-slow 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
```

- [ ] **Step 3: 创建Vite配置**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
```

- [ ] **Step 4: 提交**

```bash
git add frontend/package.json frontend/tailwind.config.ts frontend/vite.config.ts
git commit -m "chore: initialize frontend project with React 19 and Tailwind 4"
```

---

### Task 2: 创建设计令牌和主题系统

**Files:**
- Create: `frontend/src/styles/design-tokens.ts`
- Create: `frontend/src/styles/theme.css`
- Create: `frontend/src/hooks/useTheme.ts`

- [ ] **Step 1: 创建设计令牌**

```typescript
// frontend/src/styles/design-tokens.ts
export const colors = {
  background: '#0f1115',
  surface: '#181a20',
  'surface-raised': '#1e2028',
  border: '#2a2d35',
  primary: {
    DEFAULT: '#3b82f6',
    hover: '#2563eb',
  },
  success: '#22c55e',
  warning: '#eab308',
  danger: '#ef4444',
  info: '#06b6d4',
  text: {
    primary: '#f1f5f9',
    secondary: '#94a3b8',
    muted: '#64748b',
    inverse: '#0f1115',
  },
} as const

export const spacing = {
  '0.5': '2px',
  '1': '4px',
  '2': '8px',
  '3': '12px',
  '4': '16px',
  '5': '20px',
  '6': '24px',
  '8': '32px',
  '10': '40px',
  '12': '48px',
  '16': '64px',
} as const

export const borderRadius = {
  DEFAULT: '6px',
  md: '8px',
  lg: '12px',
  xl: '16px',
} as const

export const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  DEFAULT: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
} as const

export const transitions = {
  fast: '150ms cubic-bezier(0.16, 1, 0.3, 1)',
  DEFAULT: '200ms cubic-bezier(0.16, 1, 0.3, 1)',
  slow: '300ms cubic-bezier(0.16, 1, 0.3, 1)',
} as const
```

- [ ] **Step 2: 创建主题CSS**

```css
/* frontend/src/styles/theme.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: #0f1115;
    --surface: #181a20;
    --surface-raised: #1e2028;
    --border: #2a2d35;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --success: #22c55e;
    --warning: #eab308;
    --danger: #ef4444;
    --info: #06b6d4;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --text-inverse: #0f1115;
  }

  * {
    @apply border-border;
  }

  body {
    @apply bg-background text-text-primary antialiased;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  /* Scrollbar styling */
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  ::-webkit-scrollbar-track {
    background: var(--surface);
  }

  ::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 4px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
  }
}

@layer components {
  .card {
    @apply bg-surface border border-border rounded-lg shadow-sm;
  }

  .card-hover {
    @apply hover:shadow-md hover:border-border/80 transition-shadow duration-200;
  }

  .btn {
    @apply inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all duration-200;
  }

  .btn-primary {
    @apply btn bg-primary text-white hover:bg-primary-hover active:scale-[0.98];
  }

  .btn-secondary {
    @apply btn bg-surface border border-border hover:bg-surface-raised active:scale-[0.98];
  }

  .btn-ghost {
    @apply btn hover:bg-surface-raised active:scale-[0.98];
  }

  .btn-danger {
    @apply btn bg-danger text-white hover:bg-danger/90 active:scale-[0.98];
  }

  .input {
    @apply w-full px-3 py-2 bg-surface border border-border rounded-md text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors duration-200;
  }

  .input-error {
    @apply border-danger focus:ring-danger/20 focus:border-danger;
  }

  .label {
    @apply block text-sm font-medium text-text-secondary mb-1;
  }

  .error-text {
    @apply text-sm text-danger mt-1;
  }
}

@layer utilities {
  .text-balance {
    text-wrap: balance;
  }
}
```

- [ ] **Step 3: 创建主题Hook**

```typescript
// frontend/src/hooks/useTheme.ts
import { useState, useEffect, useCallback } from 'react'

type Theme = 'dark' | 'light' | 'system'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem('theme')
    return (stored as Theme) || 'dark'
  })

  useEffect(() => {
    const root = window.document.documentElement
    
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      root.classList.toggle('dark', systemTheme === 'dark')
    } else {
      root.classList.toggle('dark', theme === 'dark')
    }
    
    localStorage.setItem('theme', theme)
  }, [theme])

  const setDark = useCallback(() => setTheme('dark'), [])
  const setLight = useCallback(() => setTheme('light'), [])
  const setSystem = useCallback(() => setTheme('system'), [])

  return { theme, setTheme, setDark, setLight, setSystem }
}
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/styles/design-tokens.ts frontend/src/styles/theme.css frontend/src/hooks/useTheme.ts
git commit -m "feat: add design tokens and theme system"
```

---

### Task 3: 创建全局布局组件

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/Header.tsx`
- Create: `frontend/src/components/StatusBar.tsx`

- [ ] **Step 1: 创建布局组件**

```typescript
// frontend/src/components/Layout.tsx
import React from 'react'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { StatusBar } from './StatusBar'

export function Layout() {
  return (
    <div className="flex flex-col h-screen bg-background text-text-primary">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
      <StatusBar />
    </div>
  )
}
```

- [ ] **Step 2: 创建侧边栏**

```typescript
// frontend/src/components/Sidebar.tsx
import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { 
  Code2, 
  BarChart3, 
  FileText, 
  Database, 
  Settings,
  ChevronLeft,
  ChevronRight
} from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { to: '/', icon: Code2, label: '策略编辑' },
  { to: '/backtest', icon: BarChart3, label: '回测' },
  { to: '/reports', icon: FileText, label: '报告' },
  { to: '/data', icon: Database, label: '数据' },
  { to: '/settings', icon: Settings, label: '设置' },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <aside 
      className={`flex flex-col bg-surface border-r border-border transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      <div className="flex items-center justify-between p-4">
        {!collapsed && <span className="font-semibold text-lg">导航</span>}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded hover:bg-surface-raised transition-colors"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
      
      <nav className="flex-1 px-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.to
          
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors duration-200 ${
                isActive 
                  ? 'bg-primary/10 text-primary' 
                  : 'text-text-secondary hover:bg-surface-raised hover:text-text-primary'
              }`}
            >
              <Icon size={18} />
              {!collapsed && <span className="text-sm">{item.label}</span>}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/Layout.tsx frontend/src/components/Sidebar.tsx frontend/src/components/Header.tsx frontend/src/components/StatusBar.tsx
git commit -m "feat: add global layout components"
```

---

### Task 4: 创建shadcn/ui组件库

**Files:**
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/card.tsx`
- Create: `frontend/src/components/ui/dialog.tsx`
- Create: `frontend/src/components/ui/toast.tsx`
- Create: `frontend/src/components/ui/table.tsx`

- [ ] **Step 1: 创建Button组件**

```typescript
// frontend/src/components/ui/button.tsx
import React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed',
  {
    variants: {
      variant: {
        default: 'bg-primary text-white hover:bg-primary-hover active:scale-[0.98]',
        secondary: 'bg-surface border border-border hover:bg-surface-raised active:scale-[0.98]',
        ghost: 'hover:bg-surface-raised active:scale-[0.98]',
        danger: 'bg-danger text-white hover:bg-danger/90 active:scale-[0.98]',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-sm',
        lg: 'h-12 px-6 text-base',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'
```

- [ ] **Step 2: 创建Input组件**

```typescript
// frontend/src/components/ui/input.tsx
import React from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <input
        className={cn(
          'w-full px-3 py-2 bg-surface border border-border rounded-md text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors duration-200',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'
```

- [ ] **Step 3: 创建Card组件**

```typescript
// frontend/src/components/ui/card.tsx
import React from 'react'
import { cn } from '@/lib/utils'

export const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'bg-surface border border-border rounded-lg shadow-sm',
      className
    )}
    {...props}
  />
))
Card.displayName = 'Card'

export const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('px-6 py-4 border-b border-border', className)} {...props} />
))
CardHeader.displayName = 'CardHeader'

export const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3 ref={ref} className={cn('text-lg font-semibold', className)} {...props} />
))
CardTitle.displayName = 'CardTitle'

export const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('px-6 py-4', className)} {...props} />
))
CardContent.displayName = 'CardContent'
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/ui/
git commit -m "feat: add shadcn/ui component library"
```

---

### Task 5: 重构登录页

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/components/LoginForm.tsx`

- [ ] **Step 1: 创建登录表单**

```typescript
// frontend/src/components/LoginForm.tsx
import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from './ui/button'
import { Input } from './ui/input'

const loginSchema = z.object({
  username: z.string().min(3, '用户名至少3个字符'),
  password: z.string().min(6, '密码至少6个字符'),
})

type LoginFormData = z.infer<typeof loginSchema>

interface LoginFormProps {
  onSubmit: (data: LoginFormData) => void
  isLoading: boolean
}

export function LoginForm({ onSubmit, isLoading }: LoginFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <label className="label">用户名</label>
        <Input
          {...register('username')}
          placeholder="请输入用户名"
          autoComplete="username"
        />
        {errors.username && (
          <p className="error-text">{errors.username.message}</p>
        )}
      </div>
      
      <div>
        <label className="label">密码</label>
        <Input
          {...register('password')}
          type="password"
          placeholder="请输入密码"
          autoComplete="current-password"
        />
        {errors.password && (
          <p className="error-text">{errors.password.message}</p>
        )}
      </div>
      
      <Button
        type="submit"
        className="w-full"
        disabled={isLoading}
      >
        {isLoading ? '登录中...' : '登录'}
      </Button>
    </form>
  )
}
```

- [ ] **Step 2: 重构登录页**

```typescript
// frontend/src/pages/LoginPage.tsx
import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { LoginForm } from '../components/LoginForm'
import { useAuth } from '../hooks/useAuth'

export function LoginPage() {
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuth()

  const handleLogin = async (data: { username: string; password: string }) => {
    setIsLoading(true)
    try {
      await login(data.username, data.password)
    } catch (error) {
      console.error('Login failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-text-primary mb-2">
            EasyQuant Studio
          </h1>
          <p className="text-text-secondary">
            专业的量化策略开发平台
          </p>
        </div>
        
        <div className="bg-surface border border-border rounded-lg p-8 shadow-lg">
          <LoginForm onSubmit={handleLogin} isLoading={isLoading} />
        </div>
      </motion.div>
    </div>
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/LoginForm.tsx frontend/src/pages/LoginPage.tsx
git commit -m "feat: refactor login page with new design system"
```

---

## 自检清单

- [x] 初始化前端项目
- [x] 创建设计令牌和主题系统
- [x] 创建全局布局组件
- [x] 创建shadcn/ui组件库
- [x] 重构登录页
- [x] 响应式布局
- [x] 暗色主题
- [x] 动画效果

---

**Plan complete and saved to `docs/superpowers/plans/2025-06-06-frontend-ui-refactor.md`.**
