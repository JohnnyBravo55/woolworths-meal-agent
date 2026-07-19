/** Hosted beta NDA — keep version/prose in sync with meal_agent_api.nda */

export const NDA_VERSION = "1";

export const NDA_STORAGE_KEY = `meal_agent_nda_accepted_v${NDA_VERSION}`;

export type NdaBlock =
  | { type: "title"; text: string }
  | { type: "subtitle"; text: string }
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "bullet"; text: string }
  | { type: "numbered"; n: number; text: string }
  | { type: "rule" };

export const NDA_BLOCKS: NdaBlock[] = [
  { type: "title", text: "Unilateral Non-Disclosure Agreement" },
  { type: "subtitle", text: "Marcus Taylor" },
  { type: "heading", text: "Confidential Beta Testing Agreement" },
  {
    type: "paragraph",
    text: 'This Confidential Beta Testing Agreement ("Agreement") is entered into electronically on the date the Recipient accepts the Agreement.',
  },
  { type: "paragraph", text: "Between:" },
  { type: "paragraph", text: 'Owner: Marcus Taylor ("Owner")' },
  { type: "paragraph", text: "and" },
  {
    type: "paragraph",
    text: 'Recipient: The person accepting this Agreement ("Recipient")',
  },
  { type: "heading", text: "A. Purpose" },
  {
    type: "paragraph",
    text: 'A. Whereas, Owner is developing software applications, artificial intelligence systems, digital products, web applications, mobile applications, and related technology services (the "Business");',
  },
  {
    type: "paragraph",
    text: "B. Whereas, Recipient wishes to access Confidential Information for the purpose of product evaluation, beta testing, user testing, research, product development, feedback, consulting, or other authorised testing purposes;",
  },
  {
    type: "paragraph",
    text: "C. Whereas, Recipient agrees not to disclose, share, distribute, or communicate any Confidential Information without the express written permission of Marcus Taylor.",
  },
  {
    type: "paragraph",
    text: "In consideration of being provided access to the beta product and related information, Recipient agrees to the following terms:",
  },
  { type: "rule" },
  { type: "heading", text: "1. Confidential Information" },
  {
    type: "paragraph",
    text: '"Confidential Information" means all non-public information related to the Business, including without limitation:',
  },
  { type: "bullet", text: "software;" },
  { type: "bullet", text: "source code;" },
  { type: "bullet", text: "artificial intelligence systems;" },
  { type: "bullet", text: "AI prompts and workflows;" },
  { type: "bullet", text: "algorithms;" },
  { type: "bullet", text: "databases;" },
  { type: "bullet", text: "designs;" },
  { type: "bullet", text: "user interfaces;" },
  { type: "bullet", text: "product concepts;" },
  { type: "bullet", text: "features and functionality;" },
  { type: "bullet", text: "business plans;" },
  { type: "bullet", text: "marketing information;" },
  { type: "bullet", text: "financial information;" },
  { type: "bullet", text: "customer information;" },
  { type: "bullet", text: "documentation;" },
  { type: "bullet", text: "reports;" },
  { type: "bullet", text: "testing materials;" },
  { type: "bullet", text: "research;" },
  { type: "bullet", text: "strategies;" },
  { type: "bullet", text: "methods;" },
  { type: "bullet", text: "processes;" },
  { type: "bullet", text: "and any other information that is not publicly available." },
  {
    type: "paragraph",
    text: "Confidential Information includes information provided verbally, visually, electronically, through access to the beta application, or through any other method.",
  },
  {
    type: "paragraph",
    text: "Recipient acknowledges that all Confidential Information remains the property of Owner.",
  },
  {
    type: "paragraph",
    text: "Recipient receives no ownership rights, licence, or other rights to use Confidential Information except for the limited purpose of participating in authorised testing.",
  },
  { type: "rule" },
  { type: "heading", text: "2. Confidentiality Obligations" },
  { type: "paragraph", text: "Recipient agrees that they will not:" },
  { type: "bullet", text: "disclose Confidential Information to any person or organisation;" },
  {
    type: "bullet",
    text: "share screenshots, recordings, videos, documents, reports, or access credentials;",
  },
  { type: "bullet", text: "publish information about the beta product publicly;" },
  { type: "bullet", text: "discuss unreleased features publicly;" },
  {
    type: "bullet",
    text: "copy, reproduce, modify, reverse engineer, or distribute any part of the product;",
  },
  {
    type: "bullet",
    text: "use Confidential Information for personal, commercial, or competitive purposes.",
  },
  {
    type: "paragraph",
    text: "Recipient may only use Confidential Information for the authorised purpose of testing and providing feedback.",
  },
  {
    type: "paragraph",
    text: "These confidentiality obligations do not apply to information that:",
  },
  {
    type: "numbered",
    n: 1,
    text: "becomes publicly available through no breach of this Agreement;",
  },
  {
    type: "numbered",
    n: 2,
    text: "was already lawfully known by Recipient before disclosure;",
  },
  {
    type: "numbered",
    n: 3,
    text: "must be disclosed by law, provided Recipient gives notice to Owner where legally permitted.",
  },
  { type: "rule" },
  { type: "heading", text: "3. Beta Testing Terms" },
  { type: "paragraph", text: "Recipient understands and agrees that:" },
  { type: "bullet", text: "The product is a pre-release beta version." },
  {
    type: "bullet",
    text: "The product may contain bugs, errors, incomplete features, or changes.",
  },
  { type: "bullet", text: "Access may be removed at any time." },
  { type: "bullet", text: "Features may change or be removed before public release." },
  {
    type: "bullet",
    text: "Feedback provided during testing may be used by Owner to improve the product.",
  },
  {
    type: "bullet",
    text: "Participation does not create any employment, partnership, agency, or ownership relationship.",
  },
  {
    type: "paragraph",
    text: "Recipient agrees to provide honest and constructive feedback where possible.",
  },
  { type: "rule" },
  { type: "heading", text: "4. Intellectual Property" },
  {
    type: "paragraph",
    text: "All intellectual property associated with the product remains the sole property of Marcus Taylor.",
  },
  { type: "paragraph", text: "This includes, but is not limited to:" },
  { type: "bullet", text: "software;" },
  { type: "bullet", text: "source code;" },
  { type: "bullet", text: "designs;" },
  { type: "bullet", text: "branding;" },
  { type: "bullet", text: "trademarks;" },
  { type: "bullet", text: "AI systems;" },
  { type: "bullet", text: "prompts;" },
  { type: "bullet", text: "report structures;" },
  { type: "bullet", text: "databases;" },
  { type: "bullet", text: "processes;" },
  { type: "bullet", text: "workflows;" },
  { type: "bullet", text: "concepts;" },
  { type: "bullet", text: "documentation;" },
  { type: "bullet", text: "and any improvements or developments." },
  {
    type: "paragraph",
    text: "Recipient obtains no ownership rights or licence except the limited right to test the product during the beta period.",
  },
  { type: "rule" },
  { type: "heading", text: "5. Feedback Licence" },
  {
    type: "paragraph",
    text: "Recipient grants Owner permission to use, modify, analyse, reproduce, and incorporate any feedback, suggestions, ideas, bug reports, or recommendations provided during testing for the purpose of improving and developing the product.",
  },
  {
    type: "paragraph",
    text: "Recipient agrees that feedback may be used without compensation unless otherwise agreed in writing.",
  },
  { type: "rule" },
  { type: "heading", text: "6. Privacy" },
  {
    type: "paragraph",
    text: "Any personal information collected during beta testing will be handled in accordance with applicable New Zealand privacy laws, including the Privacy Act 2020.",
  },
  {
    type: "paragraph",
    text: "Owner will take reasonable steps to protect personal information collected during testing.",
  },
  {
    type: "paragraph",
    text: "Recipient agrees that information provided during testing may be used for:",
  },
  { type: "bullet", text: "account management;" },
  { type: "bullet", text: "product improvement;" },
  { type: "bullet", text: "analytics;" },
  { type: "bullet", text: "communication regarding the beta program." },
  { type: "rule" },
  { type: "heading", text: "7. Disclaimer and Limitation of Liability" },
  {
    type: "paragraph",
    text: 'The beta product is provided on an "as available" basis.',
  },
  { type: "paragraph", text: "Owner makes no guarantee that:" },
  { type: "bullet", text: "the product will operate without errors;" },
  { type: "bullet", text: "results generated by the product will be accurate;" },
  { type: "bullet", text: "the product will meet Recipient's expectations." },
  {
    type: "paragraph",
    text: "To the maximum extent permitted by New Zealand law, Owner will not be liable for indirect, incidental, or consequential losses arising from participation in the beta program.",
  },
  {
    type: "paragraph",
    text: "Nothing in this Agreement excludes any rights or obligations that cannot legally be excluded under New Zealand law.",
  },
  { type: "rule" },
  { type: "heading", text: "8. Breach and Remedies" },
  {
    type: "paragraph",
    text: "Recipient acknowledges that unauthorised disclosure of Confidential Information may cause serious harm to Owner.",
  },
  {
    type: "paragraph",
    text: "Owner may seek any available remedies under New Zealand law, including urgent court orders to prevent or stop unauthorised disclosure.",
  },
  { type: "rule" },
  { type: "heading", text: "9. Governing Law" },
  {
    type: "paragraph",
    text: "This Agreement is governed by the laws of New Zealand.",
  },
  {
    type: "paragraph",
    text: "If any provision of this Agreement is found to be invalid or unenforceable, the remaining provisions will continue to apply.",
  },
  { type: "rule" },
  { type: "heading", text: "Electronic Acceptance" },
  {
    type: "paragraph",
    text: 'By entering my full legal name below and selecting "I Agree", I confirm that:',
  },
  {
    type: "bullet",
    text: "I have read and understood this Confidential Beta Testing Agreement;",
  },
  { type: "bullet", text: "I agree to be legally bound by its terms;" },
  {
    type: "bullet",
    text: 'I understand that typing my name and selecting "I Agree" constitutes my electronic signature and acceptance of this Agreement.',
  },
];

export function hasAcceptedNda(): boolean {
  if (typeof window === "undefined" || !window.localStorage) return false;
  return window.localStorage.getItem(NDA_STORAGE_KEY) === "1";
}

export function markNdaAccepted(): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(NDA_STORAGE_KEY, "1");
}
