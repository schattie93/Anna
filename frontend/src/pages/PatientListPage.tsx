import { Link } from "react-router-dom";
import PatientSearch from "../components/PatientSearch";

export default function PatientListPage() {
  return (
    <div className="stack">
      <div className="page-head">
        <h1>Patienten</h1>
        <Link to="/patienten/neu" className="btn primary">
          + Neuer Patient
        </Link>
      </div>
      <PatientSearch autoFocus showAll />
    </div>
  );
}
