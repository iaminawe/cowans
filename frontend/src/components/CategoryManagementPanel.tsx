import React, { useState, useMemo } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Search, 
  FolderTree, 
  Plus, 
  Pencil, 
  Trash2, 
  ChevronRight, 
  ChevronDown,
  Image,
  Tag,
  Save,
  X,
  Upload,
  Download,
  Eye,
  Settings
} from 'lucide-react';
import { GeneratedIcon } from './IconPreviewGrid';

export interface Category {
  id: string;
  name: string;
  description?: string;
  parentId?: string;
  keywords: string[];
  iconId?: string;
  icon?: GeneratedIcon;
  children?: Category[];
  level: number;
  isExpanded?: boolean;
}

interface CategoryManagementPanelProps {
  categories: Category[];
  availableIcons: GeneratedIcon[];
  onCategoryCreate?: (parentId: string | null, name: string, description?: string) => void;
  onCategoryUpdate?: (categoryId: string, updates: Partial<Category>) => void;
  onCategoryDelete?: (categoryId: string) => void;
  onIconAssign?: (categoryId: string, iconId: string) => void;
  onIconUnassign?: (categoryId: string) => void;
  onCategoriesImport?: (file: File) => void;
  onCategoriesExport?: () => void;
  className?: string;
}

export function CategoryManagementPanel({
  categories,
  availableIcons,
  onCategoryCreate,
  onCategoryUpdate,
  onCategoryDelete,
  onIconAssign,
  onIconUnassign,
  onCategoriesImport,
  onCategoriesExport,
  className
}: CategoryManagementPanelProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showIconSelection, setShowIconSelection] = useState(false);
  const [activeTab, setActiveTab] = useState<'tree' | 'list' | 'assign'>('tree');

  // Build category tree
  const categoryTree = useMemo(() => {
    const buildTree = (parentId: string | null = null, level: number = 0): Category[] => {
      return categories
        .filter(cat => cat.parentId === parentId)
        .map(cat => ({
          ...cat,
          level,
          children: buildTree(cat.id, level + 1),
          isExpanded: expandedCategories.has(cat.id)
        }));
    };
    return buildTree();
  }, [categories, expandedCategories]);

  // Flatten categories for search and list view
  const flatCategories = useMemo(() => {
    const searchLower = searchTerm.toLowerCase();
    return categories.filter(cat => 
      cat.name.toLowerCase().includes(searchLower) ||
      cat.description?.toLowerCase().includes(searchLower) ||
      cat.keywords.some(keyword => keyword.toLowerCase().includes(searchLower))
    );
  }, [categories, searchTerm]);

  const toggleExpand = (categoryId: string) => {
    const newExpanded = new Set(expandedCategories);
    if (expandedCategories.has(categoryId)) {
      newExpanded.delete(categoryId);
    } else {
      newExpanded.add(categoryId);
    }
    setExpandedCategories(newExpanded);
  };

  const handleCategoryEdit = (category: Category) => {
    setEditingCategory(category.id);
    setSelectedCategory(category.id);
  };

  const handleIconAssignment = (categoryId: string, iconId: string) => {
    onIconAssign?.(categoryId, iconId);
    setShowIconSelection(false);
  };

  const unassignedCategories = categories.filter(cat => !cat.iconId);
  const assignedCategories = categories.filter(cat => cat.iconId);

  return (
    <Card className={cn("", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FolderTree className="h-5 w-5" />
            Category Management
            <Badge variant="secondary">{categories.length} categories</Badge>
          </CardTitle>
          <div className="flex items-center gap-2">
            {onCategoriesImport && (
              <Button variant="outline" size="sm">
                <Upload className="h-4 w-4 mr-1" />
                Import
              </Button>
            )}
            {onCategoriesExport && (
              <Button variant="outline" size="sm" onClick={onCategoriesExport}>
                <Download className="h-4 w-4 mr-1" />
                Export
              </Button>
            )}
            {onCategoryCreate && (
              <Button size="sm" onClick={() => onCategoryCreate(null, 'New Category')}>
                <Plus className="h-4 w-4 mr-1" />
                Add Category
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search categories..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="tree">Tree View</TabsTrigger>
            <TabsTrigger value="list">List View</TabsTrigger>
            <TabsTrigger value="assign">
              Icon Assignment
              <Badge variant="secondary" className="ml-2">{unassignedCategories.length}</Badge>
            </TabsTrigger>
          </TabsList>

          {/* Tree View */}
          <TabsContent value="tree" className="space-y-2">
            <div className="max-h-96 overflow-y-auto border rounded-lg p-2">
              {categoryTree.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FolderTree className="h-8 w-8 mx-auto mb-2" />
                  <p>No categories found</p>
                </div>
              ) : (
                <CategoryTreeNode
                  categories={categoryTree}
                  onToggleExpand={toggleExpand}
                  onEdit={handleCategoryEdit}
                  onDelete={onCategoryDelete}
                  onSelect={setSelectedCategory}
                  selectedId={selectedCategory}
                  editingId={editingCategory}
                />
              )}
            </div>
          </TabsContent>

          {/* List View */}
          <TabsContent value="list" className="space-y-2">
            <div className="max-h-96 overflow-y-auto space-y-2">
              {flatCategories.map((category) => (
                <CategoryListItem
                  key={category.id}
                  category={category}
                  onEdit={() => handleCategoryEdit(category)}
                  onDelete={() => onCategoryDelete?.(category.id)}
                  onSelect={() => setSelectedCategory(category.id)}
                  isSelected={selectedCategory === category.id}
                />
              ))}
            </div>
          </TabsContent>

          {/* Icon Assignment */}
          <TabsContent value="assign" className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-2 gap-4">
              <Alert>
                <Tag className="h-4 w-4" />
                <AlertDescription>
                  <div className="flex justify-between items-center">
                    <span><strong>{assignedCategories.length}</strong> categories have icons</span>
                    <Badge variant="secondary">{Math.round((assignedCategories.length / categories.length) * 100)}%</Badge>
                  </div>
                </AlertDescription>
              </Alert>
              <Alert variant="warning">
                <AlertDescription>
                  <div className="flex justify-between items-center">
                    <span><strong>{unassignedCategories.length}</strong> need icons</span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowIconSelection(true)}
                      disabled={unassignedCategories.length === 0}
                    >
                      Bulk Assign
                    </Button>
                  </div>
                </AlertDescription>
              </Alert>
            </div>

            {/* Unassigned Categories */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Categories Without Icons</Label>
              <div className="max-h-48 overflow-y-auto space-y-2">
                {unassignedCategories.map((category) => (
                  <div key={category.id} className="flex items-center justify-between p-2 border rounded">
                    <div className="flex-1">
                      <span className="font-medium text-sm">{category.name}</span>
                      {category.description && (
                        <p className="text-xs text-muted-foreground">{category.description}</p>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedCategory(category.id);
                        setShowIconSelection(true);
                      }}
                    >
                      <Image className="h-3 w-3 mr-1" />
                      Assign Icon
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Assigned Categories */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Categories With Icons</Label>
              <div className="max-h-48 overflow-y-auto space-y-2">
                {assignedCategories.map((category) => (
                  <div key={category.id} className="flex items-center justify-between p-2 border rounded">
                    <div className="flex items-center gap-3 flex-1">
                      {category.icon && (
                        <div className="w-8 h-8 rounded border flex items-center justify-center bg-gray-100 dark:bg-gray-800">
                          <img 
                            src={category.icon.thumbnailUrl} 
                            alt={category.icon.name}
                            className="w-6 h-6 object-contain"
                          />
                        </div>
                      )}
                      <div>
                        <span className="font-medium text-sm">{category.name}</span>
                        {category.icon && (
                          <p className="text-xs text-muted-foreground">{category.icon.name}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelectedCategory(category.id);
                          setShowIconSelection(true);
                        }}
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onIconUnassign?.(category.id)}
                        className="text-red-600"
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* Icon Selection Modal/Panel */}
        {showIconSelection && selectedCategory && (
          <IconSelectionPanel
            categoryId={selectedCategory}
            category={categories.find(c => c.id === selectedCategory)!}
            availableIcons={availableIcons}
            onSelect={handleIconAssignment}
            onCancel={() => setShowIconSelection(false)}
          />
        )}
      </CardContent>
    </Card>
  );
}

interface CategoryTreeNodeProps {
  categories: Category[];
  onToggleExpand: (id: string) => void;
  onEdit: (category: Category) => void;
  onDelete?: (id: string) => void;
  onSelect: (id: string) => void;
  selectedId: string | null;
  editingId: string | null;
}

function CategoryTreeNode({
  categories,
  onToggleExpand,
  onEdit,
  onDelete,
  onSelect,
  selectedId,
  editingId
}: CategoryTreeNodeProps) {
  return (
    <div className="space-y-1">
      {categories.map((category) => (
        <div key={category.id} className="space-y-1">
          <div
            className={cn(
              "flex items-center gap-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer",
              selectedId === category.id && "bg-primary/10 border border-primary/20"
            )}
            style={{ paddingLeft: `${category.level * 20 + 8}px` }}
            onClick={() => onSelect(category.id)}
          >
            {category.children && category.children.length > 0 ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-4 w-4 p-0"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleExpand(category.id);
                }}
              >
                {category.isExpanded ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
              </Button>
            ) : (
              <div className="w-4" />
            )}

            {category.icon ? (
              <div className="w-4 h-4 rounded border flex items-center justify-center bg-gray-100 dark:bg-gray-800">
                <img 
                  src={category.icon.thumbnailUrl} 
                  alt={category.icon.name}
                  className="w-3 h-3 object-contain"
                />
              </div>
            ) : (
              <div className="w-4 h-4 rounded border-2 border-dashed border-muted-foreground/30" />
            )}

            <span className="flex-1 text-sm font-medium">{category.name}</span>
            
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(category);
                }}
                className="h-6 w-6 p-0"
              >
                <Pencil className="h-3 w-3" />
              </Button>
              {onDelete && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(category.id);
                  }}
                  className="h-6 w-6 p-0 text-red-600"
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>

          {category.isExpanded && category.children && (
            <CategoryTreeNode
              categories={category.children}
              onToggleExpand={onToggleExpand}
              onEdit={onEdit}
              onDelete={onDelete}
              onSelect={onSelect}
              selectedId={selectedId}
              editingId={editingId}
            />
          )}
        </div>
      ))}
    </div>
  );
}

interface CategoryListItemProps {
  category: Category;
  onEdit: () => void;
  onDelete: () => void;
  onSelect: () => void;
  isSelected: boolean;
}

function CategoryListItem({ category, onEdit, onDelete, onSelect, isSelected }: CategoryListItemProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 p-3 border rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer",
        isSelected && "bg-primary/10 border-primary/20"
      )}
      onClick={onSelect}
    >
      {category.icon ? (
        <div className="w-8 h-8 rounded border flex items-center justify-center bg-gray-100 dark:bg-gray-800">
          <img 
            src={category.icon.thumbnailUrl} 
            alt={category.icon.name}
            className="w-6 h-6 object-contain"
          />
        </div>
      ) : (
        <div className="w-8 h-8 rounded border-2 border-dashed border-muted-foreground/30 flex items-center justify-center">
          <Image className="h-4 w-4 text-muted-foreground/50" />
        </div>
      )}

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm">{category.name}</span>
          {!category.icon && <Badge variant="outline" className="text-xs">No Icon</Badge>}
        </div>
        {category.description && (
          <p className="text-xs text-muted-foreground mb-1">{category.description}</p>
        )}
        {category.keywords.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {category.keywords.slice(0, 3).map((keyword, idx) => (
              <Badge key={idx} variant="secondary" className="text-xs px-1 py-0">
                {keyword}
              </Badge>
            ))}
            {category.keywords.length > 3 && (
              <Badge variant="secondary" className="text-xs px-1 py-0">
                +{category.keywords.length - 3}
              </Badge>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" onClick={onEdit}>
          <Pencil className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onDelete} className="text-red-600">
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

interface IconSelectionPanelProps {
  categoryId: string;
  category: Category;
  availableIcons: GeneratedIcon[];
  onSelect: (categoryId: string, iconId: string) => void;
  onCancel: () => void;
}

function IconSelectionPanel({ categoryId, category, availableIcons, onSelect, onCancel }: IconSelectionPanelProps) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredIcons = availableIcons.filter(icon =>
    icon.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    icon.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase())) ||
    category.keywords.some(keyword => 
      icon.name.toLowerCase().includes(keyword.toLowerCase()) ||
      icon.tags.some(tag => tag.toLowerCase().includes(keyword.toLowerCase()))
    )
  );

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-hidden">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Select Icon for "{category.name}"</CardTitle>
            <Button variant="ghost" size="sm" onClick={onCancel}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search icons..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>

          <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3 max-h-96 overflow-y-auto">
            {filteredIcons.map((icon) => (
              <div
                key={icon.id}
                className="aspect-square p-3 border rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer flex items-center justify-center"
                onClick={() => onSelect(categoryId, icon.id)}
              >
                <img 
                  src={icon.thumbnailUrl} 
                  alt={icon.name}
                  className="w-full h-full object-contain"
                  title={icon.name}
                />
              </div>
            ))}
          </div>

          {filteredIcons.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Image className="h-8 w-8 mx-auto mb-2" />
              <p>No icons found</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}