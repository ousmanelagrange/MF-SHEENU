import { Authenticated, Refine } from "@refinedev/core";
import routerProvider from "@refinedev/react-router";
import { App as AntApp, ConfigProvider } from "antd";
import frFR from "antd/locale/fr_FR";
import dayjs from "dayjs";
import "dayjs/locale/fr";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router";
import { AppShell } from "./components/AppShell";
import { FamilyProvider } from "./family";
import { AuditPage, MembersPage, TitlesPage } from "./pages/AdminPages";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { FamiliesPage } from "./pages/FamiliesPage";
import { HomePage } from "./pages/HomePage";
import { JoinPage } from "./pages/JoinPage";
import { KinshipPage } from "./pages/KinshipPage";
import { PersonFormPage } from "./pages/PersonFormPage";
import { PersonPage } from "./pages/PersonPage";
import { PersonsPage } from "./pages/PersonsPage";
import { TreePage } from "./pages/TreePage";
import { authProvider } from "./providers/authProvider";
import { dataProvider } from "./providers/dataProvider";
import { theme } from "./theme";

dayjs.locale("fr");

export default function App() {
  return (
    <BrowserRouter>
      <ConfigProvider theme={theme} locale={frFR}>
        <AntApp>
          <FamilyProvider>
            <Refine
              routerProvider={routerProvider}
              dataProvider={dataProvider}
              authProvider={authProvider}
              resources={[
                { name: "persons", list: "/personnes", show: "/personnes/:id", create: "/personnes/nouvelle", edit: "/personnes/:id/modifier" },
                { name: "titles", list: "/titres" },
                { name: "members", list: "/membres" },
                { name: "invitations" },
                { name: "audit", list: "/journal" },
              ]}
              options={{ disableTelemetry: true, syncWithLocation: false }}
            >
              <Routes>
                <Route path="/connexion" element={<LoginPage />} />
                <Route path="/inscription" element={<RegisterPage />} />
                <Route path="/rejoindre/:token" element={<JoinPage />} />
                <Route
                  element={
                    <Authenticated key="private" fallback={<Navigate to="/connexion" replace />}>
                      <Outlet />
                    </Authenticated>
                  }
                >
                  <Route path="/familles" element={<FamiliesPage />} />
                  <Route element={<AppShell />}>
                    <Route index element={<HomePage />} />
                    <Route path="/arbre" element={<TreePage />} />
                    <Route path="/personnes" element={<PersonsPage />} />
                    <Route path="/personnes/nouvelle" element={<PersonFormPage />} />
                    <Route path="/personnes/:id" element={<PersonPage />} />
                    <Route path="/personnes/:id/modifier" element={<PersonFormPage />} />
                    <Route path="/parente" element={<KinshipPage />} />
                    <Route path="/titres" element={<TitlesPage />} />
                    <Route path="/membres" element={<MembersPage />} />
                    <Route path="/journal" element={<AuditPage />} />
                  </Route>
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Refine>
          </FamilyProvider>
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  );
}
