'use client'

import { useRef, useState, useMemo, useCallback } from 'react'
import {
  Search,
  ArrowUp,
  ArrowDown,
  SlidersHorizontal,
  CalendarIcon,
} from 'lucide-react'
import {
  format,
  parseISO,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  subMonths,
} from 'date-fns'
import { type DateRange } from 'react-day-picker'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
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
  const [calendarOpen, setCalendarOpen] = useState(false)
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

  // Label shown on the date range trigger button
  const dateTriggerLabel = useMemo(() => {
    if (!dateFrom) return null
    if (!dateTo || dateFrom === dateTo) return format(parseISO(dateFrom), 'MMM d, yyyy')
    return `${format(parseISO(dateFrom), 'MMM d')} – ${format(parseISO(dateTo), 'MMM d, yyyy')}`
  }, [dateFrom, dateTo])

  // Hint text shown inside the popover
  const calendarHint = awaitingEndRef.current
    ? 'Now select an end date — or click the same day for a single day'
    : 'Select a start date'

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
      setCalendarOpen(false)
    }
  }, [onDateFromChange, onDateToChange])

  const applyPreset = useCallback((from: Date, to: Date) => {
    onDateFromChange(format(from, 'yyyy-MM-dd'))
    onDateToChange(format(to, 'yyyy-MM-dd'))
    awaitingEndRef.current = false
    firstClickDateRef.current = null
    setCalendarOpen(false)
  }, [onDateFromChange, onDateToChange])

  const clearDate = useCallback(() => {
    onDateFromChange(undefined)
    onDateToChange(undefined)
    awaitingEndRef.current = false
    firstClickDateRef.current = null
    setCalendarOpen(false)
  }, [onDateFromChange, onDateToChange])

  const handleSheetOpenChange = useCallback((open: boolean) => {
    if (!open) {
      awaitingEndRef.current = false
      firstClickDateRef.current = null
      setCalendarOpen(false)
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
        <SheetContent side="right" className="bg-card">
          <SheetHeader className="pb-0">
            <SheetTitle>Filters</SheetTitle>
            {activeCount > 0 && (
              <SheetDescription>{activeCount} active</SheetDescription>
            )}
            <Separator className="-mx-6 mt-4 w-[calc(100%+3rem)]" />
          </SheetHeader>

          <div className="flex-1 overflow-y-auto px-6 pt-6 pb-6 space-y-6">
            {/* Date range */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Date range
                </p>
                {(dateFrom || dateTo) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto py-0 px-1 text-xs text-muted-foreground hover:text-foreground"
                    onClick={clearDate}
                  >
                    Clear
                  </Button>
                )}
              </div>

              <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
                <PopoverTrigger
                  render={
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full h-9 justify-start gap-2 font-normal text-sm"
                    />
                  }
                >
                  <CalendarIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                  {dateTriggerLabel
                    ? <span>{dateTriggerLabel}</span>
                    : <span className="text-muted-foreground">Pick a date range</span>
                  }
                </PopoverTrigger>
                <PopoverContent align="start" className="w-auto p-3 space-y-3">
                  {/* Presets */}
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      {
                        label: 'Today',
                        from: new Date(),
                        to: new Date(),
                      },
                      {
                        label: 'This week',
                        from: startOfWeek(new Date(), { weekStartsOn: 1 }),
                        to: endOfWeek(new Date(), { weekStartsOn: 1 }),
                      },
                      {
                        label: 'This month',
                        from: startOfMonth(new Date()),
                        to: endOfMonth(new Date()),
                      },
                      {
                        label: 'Last month',
                        from: startOfMonth(subMonths(new Date(), 1)),
                        to: endOfMonth(subMonths(new Date(), 1)),
                      },
                    ].map(({ label, from, to }) => (
                      <Button
                        key={label}
                        variant="outline"
                        size="sm"
                        className="h-7 px-2.5 text-xs"
                        onClick={() => applyPreset(from, to)}
                      >
                        {label}
                      </Button>
                    ))}
                  </div>

                  {/* Status hint */}
                  <p className="text-xs text-muted-foreground">{calendarHint}</p>

                  {/* Calendar */}
                  <Calendar
                    mode="range"
                    selected={selectedRange}
                    onSelect={handleRangeSelect}
                  />
                </PopoverContent>
              </Popover>
            </div>

            <Separator />

            {/* Category */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Category
                </p>
                {category && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto py-0 px-1 text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => onCategoryChange(undefined)}
                  >
                    Clear
                  </Button>
                )}
              </div>
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
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Amount range
                </p>
                {(amountMin || amountMax) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto py-0 px-1 text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => {
                      onAmountMinChange(undefined)
                      onAmountMaxChange(undefined)
                    }}
                  >
                    Clear
                  </Button>
                )}
              </div>
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
