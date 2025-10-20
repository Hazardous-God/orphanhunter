-- Migration: Site Scanner Tables
-- Date: 2025-10-20
-- Description: Create tables for live site scanner functionality

-- Sites table to track scanned websites
CREATE TABLE IF NOT EXISTS `scanned_sites` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `domain` VARCHAR(255) NOT NULL,
    `base_url` VARCHAR(500) NOT NULL,
    `scan_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `pages_found` INT DEFAULT 0,
    `status` ENUM('scanning', 'completed', 'error') DEFAULT 'scanning',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_domain` (`domain`),
    KEY `idx_scan_date` (`scan_date`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Pages table to store individual page data
CREATE TABLE IF NOT EXISTS `scanned_pages` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `site_id` INT NOT NULL,
    `url` VARCHAR(1000) NOT NULL,
    `title` VARCHAR(500) DEFAULT NULL,
    `description` TEXT DEFAULT NULL,
    `status_code` INT DEFAULT NULL,
    `response_time` DECIMAL(8,3) DEFAULT NULL,
    `content_length` INT DEFAULT NULL,
    `content_type` VARCHAR(100) DEFAULT NULL,
    `h1_count` INT DEFAULT 0,
    `h2_count` INT DEFAULT 0,
    `internal_links_count` INT DEFAULT 0,
    `external_links_count` INT DEFAULT 0,
    `images_count` INT DEFAULT 0,
    `seo_issues` JSON DEFAULT NULL,
    `meta_robots` VARCHAR(255) DEFAULT NULL,
    `canonical_url` VARCHAR(1000) DEFAULT NULL,
    `last_modified` TIMESTAMP NULL DEFAULT NULL,
    `scan_timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`site_id`) REFERENCES `scanned_sites`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `unique_url_per_site` (`site_id`, `url`(767)),
    KEY `idx_status_code` (`status_code`),
    KEY `idx_response_time` (`response_time`),
    KEY `idx_scan_timestamp` (`scan_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Keywords table to store page keywords
CREATE TABLE IF NOT EXISTS `page_keywords` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `page_id` INT NOT NULL,
    `keyword` VARCHAR(255) NOT NULL,
    `frequency` INT DEFAULT 1,
    `position` INT DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`page_id`) REFERENCES `scanned_pages`(`id`) ON DELETE CASCADE,
    KEY `idx_keyword` (`keyword`),
    KEY `idx_frequency` (`frequency`),
    UNIQUE KEY `unique_keyword_per_page` (`page_id`, `keyword`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Links table to store page links
CREATE TABLE IF NOT EXISTS `page_links` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `page_id` INT NOT NULL,
    `target_url` VARCHAR(1000) NOT NULL,
    `link_type` ENUM('internal', 'external') NOT NULL,
    `anchor_text` TEXT DEFAULT NULL,
    `link_title` VARCHAR(500) DEFAULT NULL,
    `rel_attribute` VARCHAR(100) DEFAULT NULL,
    `is_nofollow` BOOLEAN DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`page_id`) REFERENCES `scanned_pages`(`id`) ON DELETE CASCADE,
    KEY `idx_link_type` (`link_type`),
    KEY `idx_target_url` (`target_url`(767)),
    KEY `idx_is_nofollow` (`is_nofollow`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Images table to store page images
CREATE TABLE IF NOT EXISTS `page_images` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `page_id` INT NOT NULL,
    `src_url` VARCHAR(1000) NOT NULL,
    `alt_text` TEXT DEFAULT NULL,
    `title_text` VARCHAR(500) DEFAULT NULL,
    `width` INT DEFAULT NULL,
    `height` INT DEFAULT NULL,
    `file_size` INT DEFAULT NULL,
    `format` VARCHAR(10) DEFAULT NULL,
    `is_broken` BOOLEAN DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`page_id`) REFERENCES `scanned_pages`(`id`) ON DELETE CASCADE,
    KEY `idx_format` (`format`),
    KEY `idx_is_broken` (`is_broken`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- SEO issues table for detailed tracking
CREATE TABLE IF NOT EXISTS `seo_issues` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `page_id` INT NOT NULL,
    `issue_type` VARCHAR(100) NOT NULL,
    `severity` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
    `description` TEXT NOT NULL,
    `recommendation` TEXT DEFAULT NULL,
    `is_resolved` BOOLEAN DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `resolved_at` TIMESTAMP NULL DEFAULT NULL,
    FOREIGN KEY (`page_id`) REFERENCES `scanned_pages`(`id`) ON DELETE CASCADE,
    KEY `idx_issue_type` (`issue_type`),
    KEY `idx_severity` (`severity`),
    KEY `idx_is_resolved` (`is_resolved`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Structured data table for schema markup
CREATE TABLE IF NOT EXISTS `page_structured_data` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `page_id` INT NOT NULL,
    `schema_type` VARCHAR(100) NOT NULL,
    `schema_data` JSON NOT NULL,
    `is_valid` BOOLEAN DEFAULT TRUE,
    `validation_errors` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`page_id`) REFERENCES `scanned_pages`(`id`) ON DELETE CASCADE,
    KEY `idx_schema_type` (`schema_type`),
    KEY `idx_is_valid` (`is_valid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Social media tags table
CREATE TABLE IF NOT EXISTS `page_social_tags` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `page_id` INT NOT NULL,
    `tag_type` VARCHAR(50) NOT NULL, -- og:, twitter:, etc.
    `tag_property` VARCHAR(100) NOT NULL,
    `tag_content` TEXT NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`page_id`) REFERENCES `scanned_pages`(`id`) ON DELETE CASCADE,
    KEY `idx_tag_type` (`tag_type`),
    KEY `idx_tag_property` (`tag_property`),
    UNIQUE KEY `unique_tag_per_page` (`page_id`, `tag_type`, `tag_property`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Site metrics summary table for quick access
CREATE TABLE IF NOT EXISTS `site_metrics` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `site_id` INT NOT NULL,
    `total_pages` INT DEFAULT 0,
    `crawlable_pages` INT DEFAULT 0,
    `error_pages` INT DEFAULT 0,
    `redirect_pages` INT DEFAULT 0,
    `avg_response_time` DECIMAL(8,3) DEFAULT NULL,
    `total_internal_links` INT DEFAULT 0,
    `total_external_links` INT DEFAULT 0,
    `unique_external_domains` INT DEFAULT 0,
    `total_images` INT DEFAULT 0,
    `broken_images` INT DEFAULT 0,
    `seo_issues_count` INT DEFAULT 0,
    `critical_seo_issues` INT DEFAULT 0,
    `last_updated` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`site_id`) REFERENCES `scanned_sites`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `unique_metrics_per_site` (`site_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert initial data or update existing records
INSERT IGNORE INTO `scanned_sites` (`domain`, `base_url`, `status`) 
VALUES ('example.com', 'https://example.com', 'completed');

-- Create views for common queries
CREATE OR REPLACE VIEW `site_overview` AS
SELECT 
    s.id,
    s.domain,
    s.base_url,
    s.scan_date,
    s.status,
    COALESCE(m.total_pages, 0) as total_pages,
    COALESCE(m.crawlable_pages, 0) as crawlable_pages,
    COALESCE(m.error_pages, 0) as error_pages,
    COALESCE(m.avg_response_time, 0) as avg_response_time,
    COALESCE(m.seo_issues_count, 0) as seo_issues_count
FROM `scanned_sites` s
LEFT JOIN `site_metrics` m ON s.id = m.site_id
ORDER BY s.scan_date DESC;

-- Create view for SEO issues summary
CREATE OR REPLACE VIEW `seo_issues_summary` AS
SELECT 
    s.domain,
    p.url,
    p.title,
    si.issue_type,
    si.severity,
    si.description,
    si.is_resolved,
    si.created_at
FROM `seo_issues` si
JOIN `scanned_pages` p ON si.page_id = p.id
JOIN `scanned_sites` s ON p.site_id = s.id
WHERE si.is_resolved = FALSE
ORDER BY 
    FIELD(si.severity, 'critical', 'high', 'medium', 'low'),
    si.created_at DESC;

-- Create indexes for performance
ALTER TABLE `scanned_pages` ADD INDEX `idx_title` (`title`(100));
ALTER TABLE `page_links` ADD INDEX `idx_anchor_text` (`anchor_text`(100));
ALTER TABLE `page_keywords` ADD INDEX `idx_keyword_frequency` (`keyword`, `frequency`);

-- Migration completion marker
INSERT INTO `scanned_sites` (`domain`, `base_url`, `status`, `pages_found`) 
VALUES ('migration-marker', 'migration://2025-10-20', 'completed', 0)
ON DUPLICATE KEY UPDATE 
`scan_date` = CURRENT_TIMESTAMP,
`status` = 'completed';