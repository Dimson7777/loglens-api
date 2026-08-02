import { runWorkflow, setupUser } from "../lib/workflow.js";

export const options = {
  vus: 1,
  iterations: 5,
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800", "p(99)<1500"],
    http_reqs: ["rate>2"],
  },
};

export function setup() {
  return setupUser();
}

export default function (data) {
  runWorkflow(data);
}
