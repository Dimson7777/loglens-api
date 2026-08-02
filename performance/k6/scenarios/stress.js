import { runWorkflow, setupUser } from "../lib/workflow.js";

export const options = {
  scenarios: {
    short_stress: {
      executor: "ramping-vus",
      startVUs: 5,
      stages: [
        { duration: "30s", target: 20 },
        { duration: "2m", target: 30 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1800", "p(99)<3500"],
    http_reqs: ["rate>20"],
  },
};

export function setup() {
  return setupUser();
}

export default function (data) {
  runWorkflow(data);
}
