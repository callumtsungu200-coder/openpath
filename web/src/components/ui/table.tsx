import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="-mx-6 overflow-x-auto px-6">
      <table className={cn('w-full min-w-[40rem] border-collapse text-sm', className)} {...props} />
    </div>
  )
}
export function Th({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn('border-b border-border pb-3 pr-4 text-left text-xs font-medium text-subtle last:pr-0', className)} {...props} />
}
export function Td({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('border-b border-border/60 py-3 pr-4 align-top last:pr-0', className)} {...props} />
}
