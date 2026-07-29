const SENSITIVE_KEYS: &[&str] = &[
    "password",
    "login_password",
    "new_password",
    "proxy_password",
    "proxypassword",
    "credential_secret",
    "sendkey",
    "token",
    "secret",
    "webhook",
];

pub fn redact_text(content: &str, redactions: &[String]) -> String {
    content
        .lines()
        .map(|line| redact_line(line, redactions))
        .collect::<Vec<_>>()
        .join("\n")
}

pub fn redact_line(line: &str, redactions: &[String]) -> String {
    let mut redacted = line.to_string();
    for value in redactions {
        let trimmed = value.trim();
        if trimmed.len() >= 3 {
            redacted = redacted.replace(trimmed, "***");
        }
    }

    redacted = redact_proxy_credentials(&redacted);
    if contains_sensitive_key(&redacted) {
        redact_key_value_tokens(&redacted)
    } else {
        redacted
    }
}

fn redact_proxy_credentials(value: &str) -> String {
    value
        .split_whitespace()
        .map(redact_proxy_token)
        .collect::<Vec<_>>()
        .join(" ")
}

fn redact_proxy_token(token: &str) -> String {
    if let Some(redacted) = redact_proxy_url_token(token) {
        return redacted;
    }
    redact_colon_proxy_token(token).unwrap_or_else(|| token.to_string())
}

fn redact_proxy_url_token(token: &str) -> Option<String> {
    let scheme_index = token.find("://")?;
    let scheme_prefix = token[..scheme_index].to_ascii_lowercase();
    if !scheme_prefix.ends_with("http")
        && !scheme_prefix.ends_with("https")
        && !scheme_prefix.ends_with("socks5")
    {
        return None;
    }
    let authority_start = scheme_index + 3;
    let rest = &token[authority_start..];
    let at_index = rest.find('@')?;
    let userinfo = &rest[..at_index];
    let colon_index = userinfo.find(':')?;
    Some(format!(
        "{}{}:***{}",
        &token[..authority_start],
        &userinfo[..colon_index],
        &rest[at_index..]
    ))
}

fn redact_colon_proxy_token(token: &str) -> Option<String> {
    let parts = token.split(':').collect::<Vec<_>>();
    if parts.len() != 4 || parts.iter().any(|part| part.trim().is_empty()) {
        return None;
    }
    let port = parts[1].parse::<u16>().ok()?;
    if port == 0 {
        return None;
    }
    Some(format!("{}:{}:{}:***", parts[0], parts[1], parts[2]))
}

fn contains_sensitive_key(value: &str) -> bool {
    let lowered = value.to_ascii_lowercase();
    SENSITIVE_KEYS.iter().any(|key| lowered.contains(key))
}

fn redact_key_value_tokens(value: &str) -> String {
    let mut redact_next = false;
    value
        .split_whitespace()
        .map(|token| {
            if redact_next {
                redact_next = false;
                return "***".to_string();
            }

            let redacted = redact_token(token);
            if redacted == token && is_sensitive_flag(token) {
                redact_next = true;
            }
            redacted
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn redact_token(token: &str) -> String {
    let lowered = token.to_ascii_lowercase();
    if !SENSITIVE_KEYS.iter().any(|key| lowered.contains(key)) {
        return token.to_string();
    }

    for separator in ['=', ':'] {
        if let Some((left, right)) = token.split_once(separator) {
            if !right
                .trim_matches(|ch| ch == '"' || ch == '\'' || ch == ',')
                .is_empty()
            {
                return format!("{}{}***", left, separator);
            }
        }
    }

    if is_sensitive_flag(token) {
        return token.to_string();
    }

    "***".to_string()
}

fn is_sensitive_flag(token: &str) -> bool {
    token.starts_with('-')
        && SENSITIVE_KEYS
            .iter()
            .any(|key| token.to_ascii_lowercase().contains(key))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_explicit_secret_values() {
        let line = "launch --password open-sesame --profile ok";
        let result = redact_line(line, &["open-sesame".to_string()]);

        assert_eq!(result, "launch --password *** --profile ok");
    }

    #[test]
    fn redacts_sensitive_key_value_tokens() {
        let line = "proxy_password=secret123 webhook:https://example.com/hook/abc keep=value";
        let result = redact_line(line, &[]);

        assert_eq!(result, "proxy_password=*** webhook:*** keep=value");
    }

    #[test]
    fn redacts_multiline_text() {
        let text = "ok\nsendkey=SCT123\nplain";
        let result = redact_text(text, &[]);

        assert_eq!(result, "ok\nsendkey=***\nplain");
    }

    #[test]
    fn redacts_proxy_url_passwords() {
        let line = "launch --proxy-server=socks5://proxy_user:secret123@127.0.0.1:7890 ok";
        let result = redact_line(line, &[]);

        assert_eq!(
            result,
            "launch --proxy-server=socks5://proxy_user:***@127.0.0.1:7890 ok"
        );
    }

    #[test]
    fn redacts_colon_proxy_passwords() {
        let line = "proxy=127.0.0.1:7890:user1:secret123 plain 10.0.0.1:8080:user2:secret456";
        let result = redact_line(line, &[]);

        assert_eq!(
            result,
            "proxy=127.0.0.1:7890:user1:*** plain 10.0.0.1:8080:user2:***"
        );
    }
}
