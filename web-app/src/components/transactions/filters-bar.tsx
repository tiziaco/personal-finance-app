'use client'

import { Search, ArrowUp, ArrowDown } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
  onClearAll,
  hasActiveFilters,
}: FiltersBarProps) {
  return (
    <div className="flex flex-wrap gap-3 items-end">
      {/* Search input */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Search</label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="text"
            placeholder="Search merchants…"
            value={searchInput}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 w-52"
          />
        </div>
      </div>

      {/* Date From */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">From</label>
        <Input
          type="date"
          value={dateFrom ?? ''}
          onChange={(e) => onDateFromChange(e.target.value || undefined)}
          className="w-36"
        />
      </div>

      {/* Date To */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">To</label>
        <Input
          type="date"
          value={dateTo ?? ''}
          onChange={(e) => onDateToChange(e.target.value || undefined)}
          className="w-36"
        />
      </div>

      {/* Category dropdown */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Category</label>
        <Select
          value={category ?? 'all'}
          onValueChange={(value) => {
            if (value) {
              onCategoryChange(value === 'all' ? undefined : (value as CategoryEnum))
            }
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {CATEGORY_OPTIONS.map((cat) => (
              <SelectItem key={cat} value={cat}>
                {cat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Amount Min */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Min €</label>
        <Input
          type="number"
          placeholder="0"
          value={amountMin ?? ''}
          onChange={(e) => onAmountMinChange(e.target.value || undefined)}
          className="w-24"
        />
      </div>

      {/* Amount Max */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Max €</label>
        <Input
          type="number"
          placeholder="∞"
          value={amountMax ?? ''}
          onChange={(e) => onAmountMaxChange(e.target.value || undefined)}
          className="w-24"
        />
      </div>

      {/* Sort By + Sort Order */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Sort by</label>
        <div className="flex items-center gap-1">
          <Select
            value={sortBy}
            onValueChange={(value) => {
              if (value) {
                onSortByChange(value as 'date' | 'amount' | 'merchant')
              }
            }}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date">Date</SelectItem>
              <SelectItem value="amount">Amount</SelectItem>
              <SelectItem value="merchant">Merchant</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc')}
            aria-label={sortOrder === 'asc' ? 'Sort ascending' : 'Sort descending'}
          >
            {sortOrder === 'asc' ? (
              <ArrowUp className="h-4 w-4" />
            ) : (
              <ArrowDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Clear All */}
      {hasActiveFilters && (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground invisible">Clear</label>
          <Button variant="outline" size="sm" onClick={onClearAll}>
            Clear
          </Button>
        </div>
      )}
    </div>
  )
}
