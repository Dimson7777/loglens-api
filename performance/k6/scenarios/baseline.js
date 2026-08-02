import { runWorkflow, setupUser } from "../lib/workflow.js";

export const options = {
  scenarios: {
    baseline_load: {
      executor: "ramping-vus",
      startVUs: 2,
      stages: [
        { duration: "1m", target: 5 },
        { duration: "3m", target: 10 },
        { duration: "1m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<1200", "p(99)<2500"],
    http_reqs: ["rate>10"],
  },
};

export function setup() {
  return setupUser();
}

export default function (data) {
  runWorkflow(data);
}
