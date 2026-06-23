import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

vi.mock("axios");

beforeEach(() => {
  vi.clearAllMocks();
});

describe("App", () => {
  it("renders loading state initially", () => {
    render(<App />);
    expect(screen.getByText(/DengueCast/i)).toBeInTheDocument();
    expect(screen.getByText(/MODEL MATRIX ONLINE/i)).toBeInTheDocument();
  });

  it("renders the brand header", () => {
    render(<App />);
    expect(screen.getByText(/Epidemiological Operations Center/i)).toBeInTheDocument();
  });
});
