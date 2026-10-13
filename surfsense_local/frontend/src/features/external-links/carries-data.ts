// Past this, an address's query and fragment are more than a page needs to say
// which page: room for text taken from the conversation.
const DATA_IN_ADDRESS = 100

/** True when a link's address carries enough after its path to hold the user's data. */
export function carriesData(url: URL): boolean {
  return url.search.length + url.hash.length > DATA_IN_ADDRESS
}
