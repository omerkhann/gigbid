<?php
/**
 * Plugin Name: Legacy Maintenance
 * Description: Handles custom upgrade hooks for a legacy WordPress site.
 * Version: 1.0.0
 * Author: Your Name
 */

// Exit if accessed directly
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Register custom upgrade actions.
 */
add_action('init', function () {
    // Hook into the Elementor upgrade process
    add_action('elementor/upgrade/before', 'lm_before_elementor_upgrade');
    add_action('elementor/upgrade/after', 'lm_after_elementor_upgrade');
});

/**
 * Actions to perform before Elementor upgrade.
 */
function lm_before_elementor_upgrade() {
    // Disable heavy widgets to speed up upgrade
    add_filter('elementor/widgets/available', function ($widgets) {
        $exclude = ['html', 'video'];
        return array_diff($widgets, $exclude);
    });
    // Log the start of upgrade
    error_log('Legacy Maintenance: Elementor upgrade starting.');
}

/**
 * Actions to perform after Elementor upgrade.
 */
function lm_after_elementor_upgrade() {
    // Re-enable widgets
    remove_filter('elementor/widgets/available', 'lm_before_elementor_upgrade');
    // Flush cache
    if (function_exists('wp_cache_flush')) {
        wp_cache_flush();
    }
    error_log('Legacy Maintenance: Elementor upgrade completed.');
}

/**
 * Enqueue custom CSS for maintenance mode.
 */
add_action('wp_enqueue_scripts', function () {
    wp_enqueue_style('legacy-maintenance', plugins_url('maintenance.css', __FILE__), [], '1.0.0');
});
?>
