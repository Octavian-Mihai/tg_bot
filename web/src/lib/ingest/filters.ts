import type { RawJob } from "./types";
import { normalizeText } from "./text";

const INTERNSHIP_RE = /\b(intern|interns|internship|stagiaire|stagiaires|stage|co-?op|alternance)\b/;

const TECH_RE = new RegExp(
  "\\b(" +
    [
      "software|logiciel|developer|developpeur|developpement|development|programmer|programmeur",
      "engineer|engineering|ingenieur|devops|devsecops|sre|reliability|platform|infrastructure",
      "cloud|aws|azure|gcp|kubernetes|docker|backend|back-end|frontend|front-end|full-?stack",
      "web|mobile|ios|android|api|python|java|javascript|typescript|react|node|golang|rust|c\\+\\+|\\.net",
      "cyber|cybersecurity|cybersecurite|security|securite|infosec|appsec|soc|pentest",
      "network|networking|reseau|reseaux|systems?|systemes?|sysadmin",
      "it|ti|informatique|information technology|technologies? de l'information",
      "data|donnees|machine learning|ml|ai|ia|intelligence artificielle|qa|quality assurance",
      "test|testing|automation|automatisation|analyste|analyst|embedded|firmware",
    ].join("|") +
    ")\\b",
);

export const isInternship = (j: RawJob) => INTERNSHIP_RE.test(normalizeText(j.title));
export const isTech = (j: RawJob) => TECH_RE.test(normalizeText(j.title));

/** Keep internship postings whose title is IT / cybersecurity / devops / software related. */
export const filterInternships = (jobs: RawJob[]) => jobs.filter((j) => isInternship(j) && isTech(j));
