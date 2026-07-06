PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__new_simulation` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`params` text NOT NULL,
	`skip_steps` text DEFAULT '[]' NOT NULL,
	`status` text DEFAULT 'pending_dispatch' NOT NULL,
	`compute_backend` text,
	`compute_job_id` text,
	`result_bucket` text,
	`result_key` text,
	`details` text,
	`step` text,
	`step_index` integer,
	`total_steps` integer,
	`calculation` text,
	`travel_times` text,
	`report_available` integer DEFAULT false NOT NULL,
	`error` text,
	`created_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`updated_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`dispatched_at` integer,
	`finished_at` integer,
	FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
INSERT INTO `__new_simulation`("id", "user_id", "params", "skip_steps", "status", "compute_backend", "compute_job_id", "result_bucket", "result_key", "details", "step", "step_index", "total_steps", "calculation", "travel_times", "report_available", "error", "created_at", "updated_at", "dispatched_at", "finished_at") SELECT "id", "user_id", "params", '[]', "status", 'default', "id", NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "report_available", "error", "created_at", "updated_at", "created_at", "finished_at" FROM `simulation`;--> statement-breakpoint
DROP TABLE `simulation`;--> statement-breakpoint
ALTER TABLE `__new_simulation` RENAME TO `simulation`;--> statement-breakpoint
PRAGMA foreign_keys=ON;--> statement-breakpoint
CREATE INDEX `simulation_userId_idx` ON `simulation` (`user_id`);--> statement-breakpoint
CREATE INDEX `simulation_user_createdAt_idx` ON `simulation` (`user_id`,`created_at`);--> statement-breakpoint
CREATE INDEX `simulation_status_idx` ON `simulation` (`status`);--> statement-breakpoint
CREATE INDEX `simulation_compute_idx` ON `simulation` (`compute_backend`,`compute_job_id`);
