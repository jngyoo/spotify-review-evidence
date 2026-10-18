import { sqliteTable, text } from 'drizzle-orm/sqlite-core';
export const reviews = sqliteTable('reviews', { key: text('key').primaryKey(), runId:text('run_id').notNull(), reviewId:text('review_id').notNull(), payload:text('payload').notNull() });
export const analyses = sqliteTable('analyses', { runId:text('run_id').primaryKey(), payload:text('payload').notNull() });
