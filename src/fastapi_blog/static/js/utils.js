export function getErrorMessage(error) {
  if (typeof error.detail === "string") {
    return error.detail;
  }
  if (Array.isArray(error.detail)) {
    return error.detail.map((err) => err.msg).join(". ");
  }
  return "An error occurred. Please try again.";
}
