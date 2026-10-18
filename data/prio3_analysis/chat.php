<?php
/**
 * Proxy da Responses API (Codex Ilimitado) para o chat do dashboard.
 * A chave fica no servidor (.codex_key ou CODEX_API_KEY) — o navegador nunca a vê.
 */
declare(strict_types=1);
set_time_limit(900);
ignore_user_abort(true);

$MODELOS = ['gpt-5.6-sol', 'gpt-6-astra', 'gpt-6-sol', 'gpt-6-luna'];

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
    header('Access-Control-Allow-Methods: POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type');
    http_response_code(204);
    exit;
}
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['error' => ['message' => 'use POST']]);
    exit;
}

$key = getenv('CODEX_API_KEY') ?: '';
$kf = __DIR__ . '/.codex_key';
if ($key === '' && is_file($kf)) {
    $key = trim((string) file_get_contents($kf));
}
if ($key === '') {
    http_response_code(503);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['error' => ['message' => 'CODEX_API_KEY ausente no servidor']]);
    exit;
}

$raw = file_get_contents('php://input');
$body = json_decode($raw ?: '', true);
if (!is_array($body)) {
    http_response_code(400);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['error' => ['message' => 'JSON inválido']]);
    exit;
}

$model = $body['model'] ?? 'gpt-5.6-sol';
if (!in_array($model, $MODELOS, true)) {
    $model = 'gpt-5.6-sol';
}

$payload = [
    'model' => $model,
    'stream' => !empty($body['stream']),
    'input' => $body['input'] ?? '',
];
if (!empty($body['instructions']) && is_string($body['instructions'])) {
    $payload['instructions'] = $body['instructions'];
}
if (isset($body['temperature']) && is_numeric($body['temperature'])) {
    $t = (float) $body['temperature'];
    if ($t >= 0 && $t <= 2) {
        $payload['temperature'] = $t;
    }
}

$stream = !empty($payload['stream']);
$ch = curl_init('https://api.codexilimitado.com/v1/responses');
$headers = [
    'Content-Type: application/json',
    'Authorization: Bearer ' . $key,
    'User-Agent: curl/8.7.1',
    'Accept: application/json',
];
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => $headers,
    CURLOPT_POSTFIELDS => json_encode($payload, JSON_UNESCAPED_UNICODE),
    CURLOPT_TIMEOUT => 900,
    CURLOPT_CONNECTTIMEOUT => 20,
]);

if ($stream) {
    header('Content-Type: text/event-stream; charset=utf-8');
    header('Cache-Control: no-cache, no-store');
    header('X-Accel-Buffering: no');
    while (ob_get_level() > 0) {
        ob_end_flush();
    }
    flush();
    curl_setopt($ch, CURLOPT_WRITEFUNCTION, static function ($ch, $data) {
        echo $data;
        flush();
        return strlen($data);
    });
    $ok = curl_exec($ch);
    $err = curl_error($ch);
    curl_close($ch);
    if ($ok === false && $err) {
        echo 'data: ' . json_encode(['type' => 'error', 'error' => ['message' => $err]]) . "\n\n";
        flush();
    }
    exit;
}

curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$out = curl_exec($ch);
$code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
$err = curl_error($ch);
curl_close($ch);
header('Content-Type: application/json; charset=utf-8');
if ($out === false) {
    http_response_code(502);
    echo json_encode(['error' => ['message' => $err ?: 'falha ao falar com a API']]);
    exit;
}
http_response_code($code ?: 200);
echo $out;
