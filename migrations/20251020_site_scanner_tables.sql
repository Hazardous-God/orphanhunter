-- Migration: 20251020_site_scanner_tables.sql
-- Description: Create tables for live site scanner functionality
-- Date: 2025-10-20
-- Author: OrphanHunter Development Team

-- Set character set and collation
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- Create site scanner pages table
CREATE TABLE IF NOT EXISTS `site_scanner_pages` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `url` VARCHAR(2048) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `domain` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `status_code` INT,
    `title` VARCHAR(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `description` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `keywords` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `h1_tags` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `h2_tags` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `links` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `images` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `scripts` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `stylesheets` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `content_length` INT UNSIGNED,
    `load_time` FLOAT,
    `last_modified` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `canonical_url` VARCHAR(2048) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `meta_robots` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `crawl_time` DATETIME,
    `error` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_url` (`url`(255)),
    INDEX `idx_domain` (`domain`),
    INDEX `idx_status` (`status_code`),
    INDEX `idx_crawl_time` (`crawl_time`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create site scanner crawl history table
CREATE TABLE IF NOT EXISTS `site_scanner_crawl_history` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `domain` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `start_time` DATETIME NOT NULL,
    `end_time` DATETIME,
    `total_pages` INT UNSIGNED DEFAULT 0,
    `successful_pages` INT UNSIGNED DEFAULT 0,
    `error_pages` INT UNSIGNED DEFAULT 0,
    `avg_load_time` FLOAT,
    `status` ENUM('running', 'completed', 'stopped', 'error') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'running',
    `notes` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_domain` (`domain`),
    INDEX `idx_start_time` (`start_time`),
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create site scanner issues table
CREATE TABLE IF NOT EXISTS `site_scanner_issues` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `page_id` INT UNSIGNED,
    `url` VARCHAR(2048) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `issue_type` ENUM('missing_title', 'missing_description', 'http_error', 'broken_link', 'slow_load', 'duplicate_content', 'other') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `severity` ENUM('low', 'medium', 'high', 'critical') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'medium',
    `description` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    `detected_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `resolved` TINYINT(1) DEFAULT 0,
    `resolved_at` DATETIME,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`page_id`) REFERENCES `site_scanner_pages`(`id`) ON DELETE CASCADE,
    INDEX `idx_url` (`url`(255)),
    INDEX `idx_issue_type` (`issue_type`),
    INDEX `idx_severity` (`severity`),
    INDEX `idx_resolved` (`resolved`),
    INDEX `idx_detected_at` (`detected_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create stored procedure for upserting page data
DELIMITER $$

DROP PROCEDURE IF EXISTS `upsert_scanned_page`$$
CREATE PROCEDURE `upsert_scanned_page`(
    IN p_url VARCHAR(2048),
    IN p_domain VARCHAR(255),
    IN p_status_code INT,
    IN p_title VARCHAR(512),
    IN p_description TEXT,
    IN p_keywords TEXT,
    IN p_h1_tags TEXT,
    IN p_h2_tags TEXT,
    IN p_links LONGTEXT,
    IN p_images LONGTEXT,
    IN p_scripts LONGTEXT,
    IN p_stylesheets LONGTEXT,
    IN p_content_length INT,
    IN p_load_time FLOAT,
    IN p_last_modified VARCHAR(255),
    IN p_canonical_url VARCHAR(2048),
    IN p_meta_robots VARCHAR(255),
    IN p_crawl_time DATETIME,
    IN p_error TEXT
)
BEGIN
    INSERT INTO `site_scanner_pages` (
        `url`, `domain`, `status_code`, `title`, `description`, `keywords`,
        `h1_tags`, `h2_tags`, `links`, `images`, `scripts`, `stylesheets`,
        `content_length`, `load_time`, `last_modified`, `canonical_url`,
        `meta_robots`, `crawl_time`, `error`
    ) VALUES (
        p_url, p_domain, p_status_code, p_title, p_description, p_keywords,
        p_h1_tags, p_h2_tags, p_links, p_images, p_scripts, p_stylesheets,
        p_content_length, p_load_time, p_last_modified, p_canonical_url,
        p_meta_robots, p_crawl_time, p_error
    ) ON DUPLICATE KEY UPDATE
        `status_code` = p_status_code,
        `title` = p_title,
        `description` = p_description,
        `keywords` = p_keywords,
        `h1_tags` = p_h1_tags,
        `h2_tags` = p_h2_tags,
        `links` = p_links,
        `images` = p_images,
        `scripts` = p_scripts,
        `stylesheets` = p_stylesheets,
        `content_length` = p_content_length,
        `load_time` = p_load_time,
        `last_modified` = p_last_modified,
        `canonical_url` = p_canonical_url,
        `meta_robots` = p_meta_robots,
        `crawl_time` = p_crawl_time,
        `error` = p_error,
        `updated_at` = CURRENT_TIMESTAMP;
END$$

DELIMITER ;

-- Insert default configuration if not exists
INSERT IGNORE INTO `site_scanner_crawl_history` 
    (`domain`, `start_time`, `status`, `notes`)
VALUES 
    ('example.com', NOW(), 'completed', 'Initial migration - example entry');

-- End of migration
