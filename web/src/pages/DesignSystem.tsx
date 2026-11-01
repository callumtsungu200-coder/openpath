import { BadgeCheck, Inbox } from 'lucide-react'
import type { ReactNode } from 'react'
import { OpportunityCardSkeleton } from '@/components/OpportunityCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input, Label, Select } from '@/components/ui/input'
import { EmptyState, Skeleton } from '@/components/ui/states'
import { Table, Td, Th } from '@/components/ui/table'

const COLOURS = ['background', 'shell', 'surface', 'surface-raised', 'border', 'input', 'foreground', 'muted-foreground', 'subtle-foreground', 'primary', 'accent', 'accent-soft', 'success', 'warning', 'danger']
const RADII = [['sm', '8px'], ['md', '12px'], ['lg', '16px'], ['xl', '20px'], ['2xl', '28px'], ['3xl', '36px'], ['full', 'pill']]
const SPACING = [4, 8, 12, 16, 20, 24, 32, 40, 56]

function Block({ title, children }: { title: string; children: ReactNode }) {
  return <Card><CardTitle className="mb-5">{title}</CardTitle>{children}</Card>
}

/** Living reference: every sample here renders the same components the product uses. */
export function DesignSystemPage() {
  return (
    <div>
      <h1 className="text-3xl font-light tracking-tight sm:text-4xl">Design system</h1>
      <p className="mb-6 mt-2 max-w-2xl text-muted-foreground">The tokens and components every OpenPath page is built from. Tokens live in src/index.css and components in src/components/ui.</p>
      <div className="grid gap-5 lg:grid-cols-2">
        <Block title="Colour">
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
            {COLOURS.map((c) => (
              <div key={c}>
                <div className="h-12 rounded-lg border border-border" style={{ background: `hsl(var(--${c}))` }} />
                <div className="mt-1.5 break-words text-[11px] text-muted-foreground">{c}</div>
              </div>
            ))}
          </div>
        </Block>
        <Block title="Typography">
          <p className="text-5xl font-light tracking-tight">Display</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight">Section heading</p>
          <p className="mt-3 text-xl font-semibold tracking-tight">Card title</p>
          <p className="mt-3 text-[15px]">Body text in Figtree</p>
          <p className="mt-2 text-sm text-muted-foreground">Secondary text</p>
          <p className="mt-2 text-xs text-subtle">Caption text</p>
        </Block>
        <Block title="Spacing">
          <div className="flex flex-wrap items-end gap-3">
            {SPACING.map((s) => <div key={s} className="text-center text-[11px] text-muted-foreground"><div className="mb-1 bg-accent" style={{ width: s, height: s }} />{s}</div>)}
          </div>
        </Block>
        <Block title="Border radius">
          <div className="flex flex-wrap gap-3">
            {RADII.map(([name, value]) => <div key={name} className="text-center text-[11px] text-muted-foreground"><div className={`mb-1 size-14 border border-input bg-surface-raised rounded-${name}`} />{name}, {value}</div>)}
          </div>
        </Block>
        <Block title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Primary</Button><Button variant="secondary">Secondary</Button><Button variant="outline">Outline</Button><Button variant="ghost">Ghost</Button><Button variant="danger">Danger</Button><Button disabled>Disabled</Button>
          </div>
        </Block>
        <Block title="Inputs">
          <div className="grid gap-4 sm:grid-cols-2">
            <div><Label htmlFor="ds-input">Text input</Label><Input id="ds-input" placeholder="Placeholder" /></div>
            <div><Label htmlFor="ds-select">Select</Label><Select id="ds-select"><option>Option</option></Select></div>
            <label className="flex items-center gap-3 text-sm"><Checkbox defaultChecked />Checkbox</label>
          </div>
        </Block>
        <Block title="Badges">
          <div className="flex flex-wrap gap-2">
            <Badge>Neutral</Badge><Badge variant="accent">Accent</Badge><Badge variant="success"><BadgeCheck />Success</Badge><Badge variant="warning">Warning</Badge><Badge variant="danger">Danger</Badge>
          </div>
        </Block>
        <Block title="Modal">
          <Dialog>
            <DialogTrigger asChild><Button variant="secondary">Open modal</Button></DialogTrigger>
            <DialogContent>
              <DialogTitle className="pr-10 text-lg font-semibold">Modal title</DialogTitle>
              <DialogDescription className="mt-2 text-sm text-muted-foreground">Modals sit above a dimmed page and close with Escape.</DialogDescription>
            </DialogContent>
          </Dialog>
        </Block>
        <Block title="Table">
          <Table><thead><tr><Th>Source</Th><Th>Status</Th><Th>Items</Th></tr></thead><tbody><tr><Td>Example</Td><Td><Badge variant="success">Success</Badge></Td><Td>12</Td></tr></tbody></Table>
        </Block>
        <Block title="Navigation">
          <div className="flex flex-wrap items-center gap-1">
            <span className="rounded-full bg-primary px-5 py-3 text-sm font-medium text-primary-foreground">Active</span>
            <span className="rounded-full px-5 py-3 text-sm font-medium text-muted-foreground">Inactive</span>
          </div>
        </Block>
        <Block title="Loading state"><Skeleton className="mb-3 h-4 w-1/2" /><OpportunityCardSkeleton /></Block>
        <Block title="Empty state"><EmptyState icon={Inbox} title="Nothing here yet">Empty states say why and what to do next.</EmptyState></Block>
      </div>
    </div>
  )
}
