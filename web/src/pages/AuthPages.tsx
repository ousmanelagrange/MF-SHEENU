import { useLogin, useRegister } from "@refinedev/core";
import { Alert, Button, Form, Input } from "antd";
import { Link, useSearchParams } from "react-router";
import { NtienyaCloth, Wordmark } from "../components/Ntienya";

function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth">
      <div className="auth__cloth">
        <NtienyaCloth />
        <div className="auth__cloth-caption">
          <p>Chaque nom a sa place, chaque histoire a sa voix.</p>
          <span>L'arbre, les titres et la mémoire de votre famille, réservés à ses membres.</span>
        </div>
      </div>
      <div className="auth__panel">
        <Wordmark />
        {children}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { mutate: login, isPending, error } = useLogin<{ login: string; password: string; redirectTo?: string }>();
  const [params] = useSearchParams();
  const redirectTo = params.get("suite") ?? undefined;
  return (
    <AuthLayout>
      <h1>Se connecter</h1>
      <p className="lead">Avec l'e-mail ou le numéro de téléphone utilisé à l'inscription.</p>
      {error && <Alert type="error" showIcon message={error.message} style={{ marginBottom: 16 }} />}
      <Form layout="vertical" requiredMark={false} onFinish={(v) => login({ ...v, redirectTo })}>
        <Form.Item name="login" label="E-mail ou téléphone" rules={[{ required: true, message: "Indiquez votre identifiant." }]}>
          <Input autoComplete="username" size="large" />
        </Form.Item>
        <Form.Item name="password" label="Mot de passe" rules={[{ required: true, message: "Indiquez votre mot de passe." }]}>
          <Input.Password autoComplete="current-password" size="large" />
        </Form.Item>
        <Button type="primary" htmlType="submit" size="large" block loading={isPending}>
          Se connecter
        </Button>
      </Form>
      <p style={{ marginTop: 24, color: "var(--muted)" }}>
        Pas encore de compte ? <Link to={`/inscription${redirectTo ? `?suite=${encodeURIComponent(redirectTo)}` : ""}`}>Créer un compte</Link>
      </p>
    </AuthLayout>
  );
}

export function RegisterPage() {
  const { mutate: register, isPending, error } = useRegister<{
    full_name: string;
    login: string;
    password: string;
    redirectTo?: string;
  }>();
  const [params] = useSearchParams();
  const redirectTo = params.get("suite") ?? undefined;
  return (
    <AuthLayout>
      <h1>Créer un compte</h1>
      <p className="lead">
        Vous rejoindrez ensuite votre famille grâce au lien d'invitation reçu, ou vous en créerez une.
      </p>
      {error && <Alert type="error" showIcon message={error.message} style={{ marginBottom: 16 }} />}
      <Form layout="vertical" requiredMark={false} onFinish={(v) => register({ ...v, redirectTo })}>
        <Form.Item name="full_name" label="Nom complet" rules={[{ required: true, min: 2, message: "Indiquez votre nom." }]}>
          <Input autoComplete="name" size="large" />
        </Form.Item>
        <Form.Item
          name="login"
          label="E-mail ou téléphone"
          extra="Pour un numéro, incluez l'indicatif du pays, par exemple +237."
          rules={[{ required: true, message: "Indiquez un e-mail ou un numéro." }]}
        >
          <Input autoComplete="username" size="large" />
        </Form.Item>
        <Form.Item
          name="password"
          label="Mot de passe"
          rules={[{ required: true, min: 8, message: "8 caractères au minimum." }]}
        >
          <Input.Password autoComplete="new-password" size="large" />
        </Form.Item>
        <Button type="primary" htmlType="submit" size="large" block loading={isPending}>
          Créer mon compte
        </Button>
      </Form>
      <p style={{ marginTop: 24, color: "var(--muted)" }}>
        Déjà inscrit ? <Link to={`/connexion${redirectTo ? `?suite=${encodeURIComponent(redirectTo)}` : ""}`}>Se connecter</Link>
      </p>
    </AuthLayout>
  );
}

export { AuthLayout };
