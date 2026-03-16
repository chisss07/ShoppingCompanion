import { ArrowRight, TrendingUp, TrendingDown, Repeat } from 'lucide-react';
import { clsx } from 'clsx';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { formatPrice } from '../../services/api';
import type { Alternative } from '../../types';

// ─────────────────────────────────────────────
// Relationship badge config
// ─────────────────────────────────────────────

type RelationshipConfig = {
  label: string;
  variant: 'success' | 'warning' | 'info' | 'neutral';
  icon: React.ReactNode;
};

function getRelationshipConfig(relationship: string): RelationshipConfig {
  const lower = relationship.toLowerCase();
  if (lower.includes('newer') || lower.includes('upgrade')) {
    return {
      label: 'Newer Model',
      variant: 'success',
      icon: <TrendingUp className="h-3 w-3" aria-hidden="true" />,
    };
  }
  if (lower.includes('budget') || lower.includes('cheaper') || lower.includes('older')) {
    return {
      label: 'Budget Option',
      variant: 'warning',
      icon: <TrendingDown className="h-3 w-3" aria-hidden="true" />,
    };
  }
  if (lower.includes('competitor') || lower.includes('alternative')) {
    return {
      label: 'Competitor',
      variant: 'info',
      icon: <Repeat className="h-3 w-3" aria-hidden="true" />,
    };
  }
  return {
    label: relationship,
    variant: 'neutral',
    icon: null,
  };
}

// ─────────────────────────────────────────────
// Recommendation strength indicator
// ─────────────────────────────────────────────

function StrengthDots({ strength }: { strength: Alternative['recommendation_strength'] }) {
  const levels = { strong: 3, moderate: 2, weak: 1 };
  const count = levels[strength];

  return (
    <div className="flex items-center gap-0.5" aria-label={`Recommendation strength: ${strength}`}>
      {Array.from({ length: 3 }, (_, i) => (
        <span
          key={i}
          className={clsx(
            'h-1.5 w-4 rounded-full',
            i < count
              ? strength === 'strong'
                ? 'bg-success-500'
                : strength === 'moderate'
                  ? 'bg-warning-500'
                  : 'bg-neutral-400'
              : 'bg-neutral-200',
          )}
          aria-hidden="true"
        />
      ))}
      <span className="ml-1.5 text-xs text-neutral-500 capitalize">{strength}</span>
    </div>
  );
}

// ─────────────────────────────────────────────
// AlternativeCard
// ─────────────────────────────────────────────

interface AlternativeCardProps {
  alternative: Alternative;
  onSearch: (query: string) => void;
}

export function AlternativeCard({ alternative, onSearch }: AlternativeCardProps) {
  const config = getRelationshipConfig(alternative.model_relationship);

  return (
    <article
      className="bg-white border border-neutral-200 rounded-card shadow-card p-4 flex flex-col gap-3 transition-shadow duration-200 hover:shadow-card-hover"
      aria-label={`Alternative: ${alternative.product_name}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-neutral-900 text-sm leading-tight flex-1 min-w-0">
          {alternative.product_name}
        </h3>
        <Badge variant={config.variant} className="flex-shrink-0 flex items-center gap-1">
          {config.icon}
          {config.label}
        </Badge>
      </div>

      {/* Summary */}
      <p className="text-xs text-neutral-600 leading-relaxed">
        {alternative.comparison_summary}
      </p>

      {/* Key differences */}
      {alternative.key_differences.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {alternative.key_differences.slice(0, 4).map((diff) => (
            <div
              key={diff.attribute}
              className="inline-flex items-baseline gap-1 bg-neutral-50 border border-neutral-200 rounded px-2 py-1 text-xs"
              title={`${diff.attribute}: ${diff.target} vs ${diff.alternative}`}
            >
              <span className="font-medium text-neutral-600">{diff.attribute}:</span>
              <span className="text-neutral-500 line-through">{diff.target}</span>
              <ArrowRight className="h-2.5 w-2.5 text-neutral-400 flex-shrink-0" aria-hidden="true" />
              <span className="text-primary-700 font-medium">{diff.alternative}</span>
            </div>
          ))}
        </div>
      )}

      {/* Footer row: price + strength + CTA */}
      <div className="flex items-center justify-between gap-2 pt-1 mt-auto">
        <div className="flex flex-col gap-1">
          {alternative.price_range && (
            <span className="font-mono text-sm font-semibold text-neutral-800 tabular-nums">
              From {formatPrice(alternative.price_range.min)}
            </span>
          )}
          <StrengthDots strength={alternative.recommendation_strength} />
        </div>

        <Button
          variant="ghost"
          size="sm"
          rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
          onClick={() => onSearch(alternative.product_name)}
          aria-label={`Search for ${alternative.product_name}`}
        >
          Search this
        </Button>
      </div>
    </article>
  );
}
