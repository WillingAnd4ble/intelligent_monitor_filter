export type LibraryExplanationLevel = "professional" | "student" | "kid";

export type PdfParserMode = "pypdfium" | "marker-modal";

export type UserSettings = {
  filtering_goal: string | null;
  categories: string[];
  topics: string[];
  authors: string[];
  content_interest: string[];
  library_explanation_level: LibraryExplanationLevel | string;
  notification_email: string | null;
  notification_time: string | null;
  deep_scan_limit: number;
  pdf_parser_mode: PdfParserMode | string;
};

export type SettingsUpdatePayload = Partial<{
  filtering_goal: string | null;
  categories: string[];
  topics: string[];
  authors: string[];
  content_interest: string[];
  library_explanation_level: string;
  notification_email: string | null;
  notification_time: string | null;
  deep_scan_limit: number;
  pdf_parser_mode: string;
}>;
