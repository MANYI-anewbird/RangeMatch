/**
 * Curated Demo example places with live Mireye geometry available.
 * Free-form U.S. address/coordinates remain the primary entry.
 * Selecting an example never silently substitutes another parcel for a failed lookup.
 */

export const NAMBE_VERIFIED_DEMO_ADDRESS =
  "4213 Nambe Road, Indian Hills, CO 80454";

export const NAMBE_DEMO_SCENARIO_ID = "NAMBE_CATTLE_V1";

export type DemoExamplePlace = {
  id: string;
  /** Short label for the dropdown */
  label: string;
  /** Address sent to Mireye / Advisor (use Mireye-normalized spelling) */
  address: string;
  /** Optional note shown in the option text */
  note?: string;
  /** Highlight Nambe as the verified Colorado standby exhibit */
  verifiedNambe?: boolean;
};

export const DEMO_EXAMPLE_PLACES: DemoExamplePlace[] = [
  {
    id: "nambe-co",
    label: "Nambe · Indian Hills, CO",
    address: NAMBE_VERIFIED_DEMO_ADDRESS,
    note: "Verified Demo standby",
    verifiedNambe: true,
  },
  {
    id: "mancos-co",
    label: "Mancos, CO",
    address: "45501 Road L, Mancos, CO 81328",
  },
  {
    id: "calhan-co",
    label: "Calhan, CO",
    address: "12610 Ramah Hwy, Calhan, CO 80808",
  },
  {
    id: "blanca-co",
    label: "Blanca, CO",
    address: "29833 Sanford Rd, Blanca, CO 81123",
    note: "Use Sanford (not Saford)",
  },
  {
    id: "lodi-ca",
    label: "Lodi, CA",
    address: "18000 N Skaggs Ranch Rd, Lodi, CA 95240",
    note: "Outside Colorado",
  },
];

export function findDemoExampleByAddress(
  address: string | null | undefined,
): DemoExamplePlace | undefined {
  const needle = String(address || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (!needle) return undefined;
  return DEMO_EXAMPLE_PLACES.find(
    (row) => row.address.toLowerCase().replace(/\s+/g, " ") === needle,
  );
}
