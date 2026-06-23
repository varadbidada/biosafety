import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

vi.mock("axios");

beforeEach(() => {
  vi.clearAllMocks();
});

describe("App", () => {
  it("renders landing page with brand name", () => {
    render(<App />);
    expect(screen.getAllByText(/DengueCast/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/AI-PREDICTIVE HEALTH INTELLIGENCE/i)).toBeInTheDocument();
  });

  it("renders landing page hero section", () => {
    render(<App />);
    expect(screen.getByText(/Launch Dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Prediction System/i)).toBeInTheDocument();
  });
});
