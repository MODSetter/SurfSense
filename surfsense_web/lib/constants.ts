/**
 * Application-wide constants for SurfSense web app.
 * 
 * These values are extracted from hardcoded values throughout the codebase
 * to ensure consistency and make them easier to maintain.
 * 
 * IMPORTANT: Changing these values may affect existing data. Ensure backward
 * compatibility when modifying.
 */

/**
 * Connector ID constants.
 * 
 * Default connectors use IDs 1-99 (reserved range).
 * API/dynamic connectors start from API_CONNECTOR_ID_OFFSET to avoid conflicts.
 * 
 * These IDs are used for UI identification purposes, not database IDs.
 */
export const CONNECTOR_IDS = {
  /** ID for Crawled URL connector */
  CRAWLED_URL: 1,
  /** ID for File upload connector */
  FILE: 2,
  /** ID for Browser Extension connector */
  EXTENSION: 3,
  /** ID for YouTube Video connector */
  YOUTUBE_VIDEO: 4,
  
  /**
   * Starting offset for API/dynamic connectors.
   * API connectors use IDs starting from this value to avoid conflicts
   * with hardcoded default connector IDs (1-99 reserved range).
   * 
   * Example: First API connector gets ID 1000, second gets 1001, etc.
   */
  API_CONNECTOR_ID_OFFSET: 1000,
} as const;

/**
 * Default connector configurations.
 * These are the built-in connectors that are always available.
 */
export const DEFAULT_CONNECTORS = [
  {
    id: CONNECTOR_IDS.CRAWLED_URL,
    name: "Crawled URL",
    type: "CRAWLED_URL",
  },
  {
    id: CONNECTOR_IDS.FILE,
    name: "File",
    type: "FILE",
  },
  {
    id: CONNECTOR_IDS.EXTENSION,
    name: "Extension",
    type: "EXTENSION",
  },
  {
    id: CONNECTOR_IDS.YOUTUBE_VIDEO,
    name: "Youtube Video",
    type: "YOUTUBE_VIDEO",
  },
] as const;

/**
 * Generates an ID for an API connector based on its index.
 * 
 * @param index - The index of the connector in the API connectors list
 * @returns A unique ID that doesn't conflict with default connector IDs
 */
export const getApiConnectorId = (index: number): number => {
  return CONNECTOR_IDS.API_CONNECTOR_ID_OFFSET + index;
};
