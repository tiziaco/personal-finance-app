'use client'

import { useRef, useState, useMemo, useCallback } from 'react'
import { Search, ArrowUp, ArrowDown, SlidersHorizontal } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { type DateRange } from 'react-day-picker'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'
import { type CategoryEnum, CATEGORY_OPTIONS } from '@/types/transaction'

export interface FiltersBarProps {
  searchInput: string
  onSearchChange: (value: string) => void
  dateFrom: string | undefined
  onDateFromChange: (value: string | undefined) => void
  dateTo: string | undefined
  onDateToChange: (value: string | undefined) => void
  category: CategoryEnum | undefined
  onCategoryChange: (value: CategoryEnum | undefined) => void
  amountMin: string | undefined
  onAmountMinChange: (value: string | undefined) => void
  amountMax: string | undefined
  onAmountMaxChange: (value: string | undefined) => void
  isRecurring: boolean | undefined
  onIsRecurringChange: (value: boolean | undefined) => void
  sortBy: 'date' | 'amount' | 'merchant'
  onSortByChange: (value: 'date' | 'amount' | 'merchant') => void
  sortOrder: 'asc' | 'desc'
  onSortOrderChange: (value: 'asc' | 'desc') => void
  onClearAll: () => void
  hasActiveFilters: boolean
}

export function FiltersBar({
  searchInput,
  onSearchChange,
  dateFrom,
  onDateFromChange,
  dateTo,
  onDateToChange,
  category,
  onCategoryChange,
  amountMin,
  onAmountMinChange,
  amountMax,
  onAmountMaxChange,
  isRecurring,
  onIsRecurringChange,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
  onClearAll,
  hasActiveFilters,
}: FiltersBarProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const awaitingEndRef = useRef(false)
  const firstClickDateRef = useRef<string | null>(null)

  const selectedRange = useMemo<DateRange>(() => ({
    from: dateFrom ? parseISO(dateFrom) : undefined,
    to: dateTo ? parseISO(dateTo) : undefined,
  }), [dateFrom, dateTo])

  const activeCount = [
    !!(dateFrom || dateTo),
    !!category,
    !!(amountMin || amountMax),
    isRecurring !== undefined,
  ].filter(Boolean).length

  const handleRangeSelect = useCallback((range: DateRange | undefined) => {
    if (!awaitingEndRef.current) {
      const fromStr = range?.from ? format(range.from, 'yyyy-MM-dd') : undefined
      firstClickDateRef.current = fromStr ?? null
      onDateFromChange(fromStr)
      onDateToChange(undefined)
      awaitingEndRef.current = true
    } else {
      awaitingEndRef.current = false
      if (range?.from && range?.to && range.from.getTime() !== range.to.getTime()) {
        onDateFromChange(format(range.from, 'yyyy-MM-dd'))
        onDateToChange(format(range.to, 'yyyy-MM-dd'))
      } else {
        onDateToChange(firstClickDateRef.current ?? undefined)
      }
      firstClickDateRef.current = null
    }
  }, [onDateFromChange, onDateToChange])

  const handleSheetOpenChange = useCallback((open: boolean) => {
    if (!open) {
      awaitingEndRef.current = false
      firstClickDateRef.current = null
    }
    setDrawerOpen(open)
  }, [])

  return (
    <div className="flex items-center gap-2">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
        <Input
          type="text"
          placeholder="Search merchants…"
          value={searchInput}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-8 h-9 w-52 text-sm bg-card"
        />
      </div>

      {/* Filters button */}
      <Button
        variant={activeCount > 0 ? 'default' : 'outline'}
        size="sm"
        className={cn("h-9 gap-1.5", activeCount === 0 && "bg-card")}
        onClick={() => setDrawerOpen(true)}
      >
        <SlidersHorizontal className="h-4 w-4" />
        Filters
        {activeCount > 0 && (
          <span className="flex items-center justify-center rounded-full bg-primary-foreground/20 text-primary-foreground text-[10px] font-bold w-4 h-4">
            {activeCount}
          </span>
        )}
      </Button>

      {/* Clear button */}
      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          className="h-9 text-muted-foreground hover:text-foreground"
          onClick={onClearAll}
        >
          Clear
        </Button>
      )}

      {/* Sort controls — pushed to the right */}
      <div className="flex items-center gap-1 ml-auto">
        <Select
          value={sortBy}
          onValueChange={(value) => {
            if (value) onSortByChange(value as 'date' | 'amount' | 'merchant')
          }}
        >
          <SelectTrigger className="h-9 w-28 text-sm bg-card">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="date">Date</SelectItem>
            <SelectItem value="amount">Amount</SelectItem>
            <SelectItem value="merchant">Merchant</SelectItem>
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          className="h-9 w-9 p-0 bg-card"
          onClick={() => onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc')}
          aria-label={sortOrder === 'asc' ? 'Sort ascending' : 'Sort descending'}
        >
          {sortOrder === 'asc'
            ? <ArrowUp className="h-4 w-4" />
            : <ArrowDown className="h-4 w-4" />
          }
        </Button>
      </div>

      {/* Filters Sheet */}
      <Sheet open={drawerOpen} onOpenChange={handleSheetOpenChange}>
        <SheetContent side="right">
          <SheetHeader>
            <SheetTitle>Filters</SheetTitle>
            {activeCount > 0 && (
              <SheetDescription>{activeCount} active</SheetDescription>
            )}
          </SheetHeader>

          <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
            {/* Date range */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Date range
              </p>
              <Calendar
                mode="range"
                selected={selectedRange}
                onSelect={handleRangeSelect}
              />
            </div>

            <Separator />

            {/* Category */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Category
              </p>
              <Select
                value={category ?? 'all'}
                onValueChange={(value) => {
                  if (value) onCategoryChange(value === 'all' ? undefined : (value as CategoryEnum))
                }}
              >
                <SelectTrigger className="w-full text-sm">
                  <SelectValue placeholder="All categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {CATEGORY_OPTIONS.map((cat) => (
                    <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* Amount range */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Amount range
              </p>
              <div className="flex items-end gap-2">
                <div className="flex-1 space-y-1">
                  <span className="text-xs text-muted-foreground">Min (€)</span>
                  <Input
                    type="number"
                    placeholder="0"
                    value={amountMin ?? ''}
                    onChange={(e) => onAmountMinChange(e.target.value || undefined)}
                    className="text-sm"
                  />
                </div>
                <div className="flex-1 space-y-1">
                  <span className="text-xs text-muted-foreground">Max (€)</span>
                  <Input
                    type="number"
                    placeholder="1000"
                    value={amountMax ?? ''}
                    onChange={(e) => onAmountMaxChange(e.target.value || undefined)}
                    className="text-sm"
                  />
                </div>
              </div>
            </div>

            <Separator />

            {/* Recurring only */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Recurring only</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Show only recurring transactions
                </p>
              </div>
              <Switch
                checked={isRecurring === true}
                onCheckedChange={(checked) => onIsRecurringChange(checked ? true : undefined)}
              />
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
