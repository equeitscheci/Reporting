import { createElement, useEffect, useRef } from "react";

type ECIAISpaceElement = HTMLElement & {
  accessTokenFunction?: () => Promise<string>;
};

const BASE_URL = import.meta.env.VITE_ECI_AI_WIDGET_BASE_URL ?? "https://ai-api.ecinexus.com";
const INTEGRATION_ID =
  import.meta.env.VITE_ECI_AI_WIDGET_INTEGRATION_ID ?? "3875399b-3089-4239-9d86-9ec7d5d98c91";
const AGENT_ID = import.meta.env.VITE_ECI_AI_WIDGET_AGENT_ID ?? "1fce2ec2-9097-424f-b5b2-f5ea430a248d";
const MODE = import.meta.env.VITE_ECI_AI_WIDGET_MODE ?? "fab";
const TOKEN_ENDPOINT = import.meta.env.VITE_ECI_AI_WIDGET_TOKEN_ENDPOINT ?? "/api/.ai/token";

export function ECIAgentWidget() {
  const ref = useRef<ECIAISpaceElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;

    ref.current.accessTokenFunction = async () => {
      const response = await fetch(TOKEN_ENDPOINT, { credentials: "include" });
      if (!response.ok) {
        throw new Error(`Unable to get ECI AI widget token: ${response.status}`);
      }

      const body = (await response.json()) as { access_token?: string };
      if (!body.access_token) {
        throw new Error("ECI AI widget token response did not include access_token");
      }
      return body.access_token;
    };
  }, []);

  return createElement("eci-ai-space", {
    id: "ai-widget",
    ref,
    "base-url": BASE_URL,
    "integration-id": INTEGRATION_ID,
    "agent-id": AGENT_ID,
    mode: MODE,
  });
}
