import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Download, X, ExternalLink, Heart, Copy, RefreshCw, Palette } from 'lucide-react';
import { GeneratedIcon } from './IconPreviewGrid';

interface IconPreviewModalProps {
  icon: GeneratedIcon | null;
  isOpen: boolean;
  onClose: () => void;
  onDownload?: (iconId: string) => void;
  onFavorite?: (iconId: string, favorite: boolean) => void;
  onRegenerate?: (iconId: string, style: string) => void;
  isRegenerating?: boolean;
}

export function IconPreviewModal({
  icon,
  isOpen,
  onClose,
  onDownload,
  onFavorite,
  onRegenerate,
  isRegenerating = false
}: IconPreviewModalProps) {
  const [showStyleOptions, setShowStyleOptions] = useState(false);
  const [selectedStyle, setSelectedStyle] = useState<string>('');

  if (!icon) return null;

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(icon.imageUrl);
    // You could add a toast notification here
  };

  const handleRegenerate = () => {
    if (onRegenerate) {
      onRegenerate(icon.id, selectedStyle || icon.style);
      setShowStyleOptions(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between pr-10">
            <span>{icon.name}</span>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{icon.style}</Badge>
              <Badge variant="outline">{icon.size}px</Badge>
              <Badge variant="outline">{icon.format}</Badge>
            </div>
          </DialogTitle>
          <DialogDescription>
            {icon.categoryName} • Generated {new Date(icon.generatedAt).toLocaleDateString()}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto">
          <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-8 flex items-center justify-center min-h-[400px] relative">
            {isRegenerating && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center rounded-lg">
                <div className="text-white text-center">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2" />
                  <p>Regenerating icon...</p>
                </div>
              </div>
            )}
            <img
              src={icon.imageUrl}
              alt={icon.name}
              className="max-w-full max-h-[600px] object-contain"
            />
          </div>

          {showStyleOptions && (
            <div className="mt-4 p-4 bg-muted rounded-lg">
              <h4 className="font-medium mb-2 flex items-center gap-2">
                <Palette className="w-4 h-4" />
                Regenerate with Different Style
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="style-select">Style</Label>
                  <Select 
                    value={selectedStyle || icon.style} 
                    onValueChange={setSelectedStyle}
                  >
                    <SelectTrigger id="style-select">
                      <SelectValue placeholder="Select style" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="modern">Modern</SelectItem>
                      <SelectItem value="flat">Flat</SelectItem>
                      <SelectItem value="outlined">Outlined</SelectItem>
                      <SelectItem value="minimal">Minimal</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end gap-2">
                  <Button
                    onClick={handleRegenerate}
                    disabled={isRegenerating}
                    className="flex-1"
                  >
                    <RefreshCw className={`w-4 h-4 mr-2 ${isRegenerating ? 'animate-spin' : ''}`} />
                    Regenerate
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowStyleOptions(false);
                      setSelectedStyle('');
                    }}
                    disabled={isRegenerating}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <h4 className="font-medium mb-2">Details</h4>
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Category:</dt>
                  <dd>{icon.categoryName}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Style:</dt>
                  <dd>{icon.style}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Size:</dt>
                  <dd>{icon.size}px</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Format:</dt>
                  <dd className="uppercase">{icon.format}</dd>
                </div>
              </dl>
            </div>

            {icon.tags && icon.tags.length > 0 && (
              <div>
                <h4 className="font-medium mb-2">Tags</h4>
                <div className="flex flex-wrap gap-1">
                  {icon.tags.map((tag, index) => (
                    <Badge key={index} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="flex-row justify-between">
          <div className="flex gap-2">
            <Button
              variant={icon.isFavorite ? "default" : "outline"}
              size="sm"
              onClick={() => onFavorite?.(icon.id, !icon.isFavorite)}
            >
              <Heart className={`w-4 h-4 mr-2 ${icon.isFavorite ? 'fill-current' : ''}`} />
              {icon.isFavorite ? 'Favorited' : 'Favorite'}
            </Button>
            {onRegenerate && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowStyleOptions(!showStyleOptions)}
                disabled={isRegenerating}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Regenerate
              </Button>
            )}
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyUrl}
            >
              <Copy className="w-4 h-4 mr-2" />
              Copy URL
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(icon.imageUrl, '_blank')}
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              Open Original
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => onDownload?.(icon.id)}
            >
              <Download className="w-4 h-4 mr-2" />
              Download
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}