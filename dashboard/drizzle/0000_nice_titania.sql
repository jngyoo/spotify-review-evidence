CREATE TABLE `analyses` (
	`run_id` text PRIMARY KEY NOT NULL,
	`payload` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `reviews` (
	`key` text PRIMARY KEY NOT NULL,
	`run_id` text NOT NULL,
	`review_id` text NOT NULL,
	`payload` text NOT NULL
);
