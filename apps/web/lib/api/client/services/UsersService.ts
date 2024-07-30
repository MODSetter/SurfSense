/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { User } from "../models/User";
import type { UserCreate } from "../models/UserCreate";
import type { UserSearchResults } from "../models/UserSearchResults";
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class UsersService {
  /**
   * Get User
   * Returns a user from a user_id.
   *
   * **Returns:**
   * - User: User object.
   * @returns User Successful Response
   * @throws ApiError
   */
  public static usersGetUser({
    userId,
  }: {
    userId: string;
  }): CancelablePromise<User> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/users/get/",
      query: {
        user_id: userId,
      },
      errors: {
        404: `Not found`,
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get All Users
   * Returns a list of all users.
   *
   * **Returns:**
   * - list[User]: List of all users.
   * @returns User Successful Response
   * @throws ApiError
   */
  public static usersGetAllUsers(): CancelablePromise<Array<User>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/users/get-all/",
      errors: {
        404: `Not found`,
      },
    });
  }
  /**
   * Search Users
   * Search for users based on a keyword and return the top `max_results` items.
   *
   * **Args:**
   * - keyword (str, optional): The keyword to search for. Defaults to None.
   * - max_results (int, optional): The maximum number of search results to return. Defaults to 10.
   * - search_on (str, optional): The field to perform the search on. Defaults to "email".
   *
   * **Returns:**
   * - UserSearchResults: Object containing a list of the top `max_results` items that match the keyword.
   * @returns UserSearchResults Successful Response
   * @throws ApiError
   */
  public static usersSearchUsers({
    searchOn = "email",
    keyword,
    maxResults,
  }: {
    searchOn?: "id" | "email" | "forename" | "surname";
    keyword?: string | number | null;
    maxResults?: number | null;
  }): CancelablePromise<UserSearchResults> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/users/search/",
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
  /**
   * Create User
   * Craete a new user.
   *
   * **Args:**
   * - user_in (UserCreate): JSON of the user to create. Forename, surname and email. Email must be unique.
   *
   * **Returns:**
   * - User: User object
   * @returns User Successful Response
   * @throws ApiError
   */
  public static usersCreateUser({
    requestBody,
  }: {
    requestBody: UserCreate;
  }): CancelablePromise<User> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/users/create",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        404: `Not found`,
        422: `Validation Error`,
      },
    });
  }
}
