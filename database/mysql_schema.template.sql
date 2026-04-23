-- Template only.
-- Do not import this file directly in MySQL clients.
-- The application reads this file and replaces:
--   {database_name}
--   {charset}
-- at runtime before executing the statements.

CREATE DATABASE IF NOT EXISTS `{database_name}`
  CHARACTER SET {charset}
  COLLATE {charset}_unicode_ci;

USE `{database_name}`;

CREATE TABLE IF NOT EXISTS `article_tasks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Task ID returned by the API',
  `category` VARCHAR(16) NOT NULL COMMENT 'Article mode: seo or geo',
  `keyword` TEXT NOT NULL COMMENT 'Keyword for mode 1, outline content for mode 2',
  `mode_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '1 keyword mode, 2 outline mode',
  `info` TEXT NOT NULL COMMENT 'Brand / product / business context',
  `task_context_json` LONGTEXT NOT NULL COMMENT 'Normalized task context as JSON',
  `language` VARCHAR(32) NOT NULL DEFAULT 'English' COMMENT 'Requested article language',
  `provider` VARCHAR(32) NOT NULL DEFAULT 'openai' COMMENT 'LLM provider: openai or anthropic',
  `word_limit` INT UNSIGNED NOT NULL DEFAULT 1200 COMMENT 'Target text length limit (excluding image content)',
  `force_refresh` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Ignore reusable cache when 1',
  `include_cover` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT 'Whether to generate a cover image: 0 or 1',
  `content_image_count` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Number of body images to generate: 0-3',
  `access_tier` VARCHAR(32) NOT NULL DEFAULT 'standard' COMMENT 'Access tier derived from the bearer token',
  `cache_key` CHAR(64) NOT NULL COMMENT 'Reusable cache key based on category + keyword + mode_type + info',
  `status` VARCHAR(32) NOT NULL DEFAULT 'queued' COMMENT 'queued, running, completed, failed',
  `cache_hit` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Whether the article result came from cache',
  `error_message` TEXT NULL COMMENT 'Failure reason when status=failed',
  `created_at` DATETIME(6) NOT NULL COMMENT 'UTC task creation time',
  `updated_at` DATETIME(6) NOT NULL COMMENT 'UTC last update time',
  `completed_at` DATETIME(6) NULL COMMENT 'UTC completion time',
  PRIMARY KEY (`id`),
  KEY `idx_article_tasks_status_created` (`status`, `created_at`),
  KEY `idx_article_tasks_cache_key` (`cache_key`),
  KEY `idx_article_tasks_completed_at` (`completed_at`)
) ENGINE=InnoDB DEFAULT CHARSET={charset} COMMENT='Async article generation tasks';

CREATE TABLE IF NOT EXISTS `article_task_results` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Result row ID',
  `task_id` BIGINT UNSIGNED NOT NULL COMMENT 'Foreign key to article_tasks.id',
  `article_title` VARCHAR(512) NULL COMMENT 'Generated article title',
  `meta_title` VARCHAR(512) NULL COMMENT 'Generated meta title',
  `meta_description` TEXT NULL COMMENT 'Generated meta description',
  `generation_mode` VARCHAR(32) NULL COMMENT 'Text generation mode, such as mock or llm',
  `image_generation_mode` VARCHAR(32) NULL COMMENT 'Image generation mode, such as disabled, mock, azure',
  `article_json` LONGTEXT NOT NULL COMMENT 'Full article payload returned by the writer service',
  `created_at` DATETIME(6) NOT NULL COMMENT 'UTC initial result save time',
  `updated_at` DATETIME(6) NOT NULL COMMENT 'UTC latest result update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_article_task_results_task_id` (`task_id`),
  CONSTRAINT `fk_article_task_results_task_id`
    FOREIGN KEY (`task_id`) REFERENCES `article_tasks` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET={charset} COMMENT='Generated article result payloads';
