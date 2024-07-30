/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Spell } from "../models/Spell";
import type { SpellSearchResults } from "../models/SpellSearchResults";
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class SpellsService {
  /**
   * Get Spell
   * Returns a spell from a spell_id.
   *
   * **Returns:**
   * - spell: spell object.
   * @returns Spell Successful Response
   * @throws ApiError
   */
  public static spellsGetSpell({
    spellId,
  }: {
    spellId: string;
  }): CancelablePromise<Spell> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/spells/get/",
      query: {
        spell_id: spellId,
      },
      errors: {
        404: `Not found`,
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get All Spells
   * Returns a list of all spells.
   *
   * **Returns:**
   * - list[spell]: List of all spells.
   * @returns Spell Successful Response
   * @throws ApiError
   */
  public static spellsGetAllSpells(): CancelablePromise<Array<Spell>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/spells/get-all/",
      errors: {
        404: `Not found`,
      },
    });
  }
  /**
   * Search Spells
   * Search for spells based on a keyword and return the top `max_results` items.
   *
   * **Args:**
   * - keyword (str, optional): The keyword to search for. Defaults to None.
   * - max_results (int, optional): The maximum number of search results to return. Defaults to 10.
   * - search_on (str, optional): The field to perform the search on. Defaults to "email".
   *
   * **Returns:**
   * - spellSearchResults: Object containing a list of the top `max_results` items that match the keyword.
   * @returns SpellSearchResults Successful Response
   * @throws ApiError
   */
  public static spellsSearchSpells({
    searchOn = "spells",
    keyword,
    maxResults,
  }: {
    searchOn?: "id" | "spells" | "description";
    keyword?: string | number | null;
    maxResults?: number | null;
  }): CancelablePromise<SpellSearchResults> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/spells/search/",
      query: {
        search_on: searchOn,
        keyword: keyword,
        max_results: maxResults,
      },
      errors: {
        404: `Not found`,
        422: `Validation Error`,
      },
    });
  }
}
