import React, { useState, useMemo } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Search, 
  Download, 
  Trash2, 
  Eye, 
  Grid3X3, 
  List, 
  Filter,
  CheckCircle2,
  Circle,
  MoreHorizontal,
  Star,
  StarOff,
  Palette,
  Settings,
  Share2
} from 'lucide-react';

export interface GeneratedIcon {
  id: string;
  categoryId: string;
  categoryName: string;
  name: string;
  description?: string;
  style: string;
  size: string;
  format: string;
  svgContent?: string;
  imageUrl: string;
  thumbnailUrl: string;
  generatedAt: string;
  variants?: GeneratedIcon[];
  isFavorite?: boolean;
  isSelected?: boolean;
  tags: string[];
  colorScheme: string;
}

interface IconPreviewGridProps {
  icons: GeneratedIcon[];
  onIconSelect?: (iconId: string, selected: boolean) => void;
  onIconFavorite?: (iconId: string, favorite: boolean) => void;
  onIconDelete?: (iconId: string) => void;
  onIconDownload?: (iconId: string) => void;
  onBulkDownload?: (iconIds: string[]) => void;
  onBulkDelete?: (iconIds: string[]) => void;
  onPreview?: (icon: GeneratedIcon) => void;
  selectedIcons?: string[];
  viewMode?: 'grid' | 'list';
  onViewModeChange?: (mode: 'grid' | 'list') => void;
  className?: string;
}

export function IconPreviewGrid({
  icons,
  onIconSelect,
  onIconFavorite,
  onIconDelete,
  onIconDownload,
  onBulkDownload,
  onBulkDelete,
  onPreview,
  selectedIcons = [],
  viewMode = 'grid',
  onViewModeChange,
  className
}: IconPreviewGridProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [styleFilter, setStyleFilter] = useState<string>('all');
  const [sizeFilter, setSizeFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [sortBy, setSortBy] = useState<'name' | 'date' | 'category'>('date');

  const filteredIcons = useMemo(() => {
    let filtered = icons.filter(icon => {
      const matchesSearch = icon.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           icon.categoryName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           icon.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));
      
      const matchesStyle = styleFilter === 'all' || icon.style === styleFilter;
      const matchesSize = sizeFilter === 'all' || icon.size === sizeFilter;
      const matchesCategory = categoryFilter === 'all' || icon.categoryId === categoryFilter;
      const matchesFavorites = !favoritesOnly || icon.isFavorite;

      return matchesSearch && matchesStyle && matchesSize && matchesCategory && matchesFavorites;
    });

    // Sort filtered results
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'category':
          return a.categoryName.localeCompare(b.categoryName);
        case 'date':
        default:
          return new Date(b.generatedAt).getTime() - new Date(a.generatedAt).getTime();
      }
    });

    return filtered;
  }, [icons, searchTerm, styleFilter, sizeFilter, categoryFilter, favoritesOnly, sortBy]);

  const uniqueStyles = useMemo(() => 
    Array.from(new Set(icons.map(icon => icon.style))), [icons]);
  
  const uniqueSizes = useMemo(() => 
    Array.from(new Set(icons.map(icon => icon.size))), [icons]);
  
  const uniqueCategories = useMemo(() => 
    Array.from(new Set(icons.map(icon => ({ id: icon.categoryId, name: icon.categoryName })))), [icons]);

  const handleSelectAll = () => {
    const allIds = filteredIcons.map(icon => icon.id);
    allIds.forEach(id => onIconSelect?.(id, true));
  };

  const handleDeselectAll = () => {
    selectedIcons.forEach(id => onIconSelect?.(id, false));
  };

  const selectedCount = selectedIcons.length;
  const totalCount = filteredIcons.length;

  return (
    <Card className={cn("", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            Generated Icons
            <Badge variant="secondary">{totalCount} icons</Badge>
          </CardTitle>
          <div className="flex items-center gap-2">
            {selectedCount > 0 && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onBulkDownload?.(selectedIcons)}
                >
                  <Download className="h-4 w-4 mr-1" />
                  Download ({selectedCount})
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onBulkDelete?.(selectedIcons)}
                  className="text-red-600"
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Delete ({selectedCount})
                </Button>
              </>
            )}
            {onViewModeChange && (
              <div className="flex items-center border rounded-md">
                <Button
                  variant={viewMode === 'grid' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => onViewModeChange('grid')}
                  className="rounded-r-none"
                >
                  <Grid3X3 className="h-4 w-4" />
                </Button>
                <Button
                  variant={viewMode === 'list' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => onViewModeChange('list')}
                  className="rounded-l-none"
                >
                  <List className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search icons..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>

          <Select value={styleFilter} onValueChange={setStyleFilter}>
            <SelectTrigger>
              <SelectValue placeholder="All styles" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Styles</SelectItem>
              {uniqueStyles.map(style => (
                <SelectItem key={style} value={style}>{style}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sizeFilter} onValueChange={setSizeFilter}>
            <SelectTrigger>
              <SelectValue placeholder="All sizes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Sizes</SelectItem>
              {uniqueSizes.map(size => (
                <SelectItem key={size} value={size}>{size}px</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger>
              <SelectValue placeholder="All categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              {uniqueCategories.map(category => (
                <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sortBy} onValueChange={(value) => setSortBy(value as any)}>
            <SelectTrigger>
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date">Date</SelectItem>
              <SelectItem value="name">Name</SelectItem>
              <SelectItem value="category">Category</SelectItem>
            </SelectContent>
          </Select>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="favorites"
              checked={favoritesOnly}
              onCheckedChange={(checked) => setFavoritesOnly(checked === true)}
            />
            <Label htmlFor="favorites" className="text-sm">Favorites only</Label>
          </div>
        </div>

        {/* Selection Controls */}
        {totalCount > 0 && (
          <div className="flex items-center justify-between py-2 border-t border-b">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="sm" onClick={handleSelectAll}>
                Select All ({totalCount})
              </Button>
              {selectedCount > 0 && (
                <Button variant="ghost" size="sm" onClick={handleDeselectAll}>
                  Deselect All
                </Button>
              )}
            </div>
            {selectedCount > 0 && (
              <Badge variant="secondary">
                {selectedCount} selected
              </Badge>
            )}
          </div>
        )}

        {/* Icons Grid/List */}
        {filteredIcons.length === 0 ? (
          <div className="text-center py-12">
            <Palette className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No icons found</h3>
            <p className="text-muted-foreground">
              {searchTerm || styleFilter !== 'all' || sizeFilter !== 'all' || categoryFilter !== 'all' || favoritesOnly
                ? 'Try adjusting your filters'
                : 'Generate some icons to see them here'
              }
            </p>
          </div>
        ) : (
          <div className={cn(
            viewMode === 'grid' 
              ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
              : "space-y-2"
          )}>
            {filteredIcons.map((icon) => (
              <IconPreviewCard
                key={icon.id}
                icon={icon}
                isSelected={selectedIcons.includes(icon.id)}
                viewMode={viewMode}
                onSelect={(selected) => onIconSelect?.(icon.id, selected)}
                onFavorite={(favorite) => onIconFavorite?.(icon.id, favorite)}
                onDelete={() => onIconDelete?.(icon.id)}
                onDownload={() => onIconDownload?.(icon.id)}
                onPreview={() => onPreview?.(icon)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface IconPreviewCardProps {
  icon: GeneratedIcon;
  isSelected: boolean;
  viewMode: 'grid' | 'list';
  onSelect: (selected: boolean) => void;
  onFavorite: (favorite: boolean) => void;
  onDelete: () => void;
  onDownload: () => void;
  onPreview: () => void;
}

function IconPreviewCard({
  icon,
  isSelected,
  viewMode,
  onSelect,
  onFavorite,
  onDelete,
  onDownload,
  onPreview
}: IconPreviewCardProps) {
  if (viewMode === 'list') {
    return (
      <div className={cn(
        "flex items-center p-3 rounded-lg border hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors",
        isSelected && "bg-primary/10 border-primary/20"
      )}>
        <Checkbox
          checked={isSelected}
          onCheckedChange={onSelect}
          className="mr-3"
        />
        
        <div 
          className="w-12 h-12 rounded-md border flex items-center justify-center bg-background mr-4 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
          onClick={onPreview}
        >
          <img 
            src={icon.thumbnailUrl} 
            alt={icon.name}
            className="w-8 h-8 object-contain"
          />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium text-sm truncate">{icon.name}</h4>
            <Badge variant="outline" className="text-xs">{icon.style}</Badge>
            <Badge variant="outline" className="text-xs">{icon.size}px</Badge>
          </div>
          <p className="text-xs text-muted-foreground mb-1 truncate">{icon.categoryName}</p>
          <p className="text-xs text-muted-foreground">
            {new Date(icon.generatedAt).toLocaleDateString()}
          </p>
        </div>
        
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onFavorite(!icon.isFavorite)}
            className="text-yellow-600"
          >
            {icon.isFavorite ? <Star className="h-4 w-4 fill-current" /> : <StarOff className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="sm" onClick={onDownload}>
            <Download className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete} className="text-red-600">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "group relative rounded-lg border bg-card hover:shadow-md transition-all cursor-pointer",
      isSelected && "ring-2 ring-primary ring-offset-2"
    )}>
      <div className="absolute top-2 left-2 z-10">
        <Checkbox
          checked={isSelected}
          onCheckedChange={onSelect}
          className="bg-background border-border"
        />
      </div>
      
      <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onFavorite(!icon.isFavorite)}
          className="h-8 w-8 p-0 bg-background hover:bg-muted text-yellow-600"
        >
          {icon.isFavorite ? <Star className="h-4 w-4 fill-current" /> : <StarOff className="h-4 w-4" />}
        </Button>
      </div>
      
      <div 
        className="aspect-square p-6 flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-t-lg"
        onClick={onPreview}
      >
        <img 
          src={icon.imageUrl} 
          alt={icon.name}
          className="max-w-full max-h-full object-contain"
        />
      </div>
      
      <div className="p-3">
        <div className="flex items-center gap-1 mb-2">
          <h4 className="font-medium text-sm truncate flex-1">{icon.name}</h4>
        </div>
        <div className="flex items-center gap-1 mb-2">
          <Badge variant="outline" className="text-xs">{icon.style}</Badge>
          <Badge variant="outline" className="text-xs">{icon.size}px</Badge>
        </div>
        <p className="text-xs text-muted-foreground mb-2 truncate">{icon.categoryName}</p>
        
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button variant="ghost" size="sm" onClick={onDownload} className="flex-1">
            <Download className="h-3 w-3 mr-1" />
            Download
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete} className="text-red-600">
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
    </div>
  );
}