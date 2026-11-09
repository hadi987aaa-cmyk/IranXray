package com.v2ray.ang.ui.server

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.v2ray.ang.R
import com.v2ray.ang.core.CfScanResult
import com.v2ray.ang.ui.compose.FormTextField

/**
 * Scans Cloudflare edge addresses for one that still completes a TLS handshake with the
 * profile's SNI, and hands the chosen one back to the editor.
 *
 * The scan starts as soon as the dialog opens with a usable host, because that is the only
 * reason to open it.
 */
@Composable
fun CfScanDialog(
    initialSni: String,
    state: CfScanState,
    onStart: (String) -> Unit,
    onStop: () -> Unit,
    onPick: (CfScanResult) -> Unit,
    onDismiss: () -> Unit,
) {
    var sni by rememberSaveable { mutableStateOf(initialSni) }

    LaunchedEffect(Unit) {
        if (sni.isNotBlank()) onStart(sni)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.cf_scan_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                FormTextField(
                    label = stringResource(R.string.cf_scan_sni_label),
                    value = sni,
                    onValueChange = { sni = it },
                    enabled = !state.running,
                )
                if (state.running) {
                    LinearProgressIndicator(
                        progress = {
                            if (state.total == 0) 0f else state.done.toFloat() / state.total
                        },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text(
                        text = stringResource(R.string.cf_scan_progress, state.done, state.total),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                state.problem?.let { problem ->
                    Text(
                        text = stringResource(
                            when (problem) {
                                CfScanProblem.MISSING_SNI -> R.string.cf_scan_missing_sni
                                CfScanProblem.NO_CANDIDATES -> R.string.cf_scan_no_candidates
                            }
                        ),
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                if (!state.running && state.finished && state.problem == null) {
                    if (state.results.isEmpty()) {
                        Text(
                            text = stringResource(R.string.cf_scan_empty),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    } else {
                        LazyColumn(modifier = Modifier.heightIn(max = 280.dp)) {
                            items(state.results, key = { "${it.address}:${it.port}" }) { result ->
                                CfScanResultRow(result) { onPick(result) }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            if (state.running) {
                TextButton(onClick = onStop) { Text(stringResource(R.string.cf_scan_stop)) }
            } else {
                TextButton(onClick = { onStart(sni) }) { Text(stringResource(R.string.cf_scan_start)) }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.action_cancel)) }
        },
    )
}

@Composable
private fun CfScanResultRow(result: CfScanResult, onClick: () -> Unit) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(vertical = 10.dp, horizontal = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "${result.address}:${result.port}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = stringResource(R.string.cf_scan_latency, result.latencyMs),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
        HorizontalDivider()
    }
}
