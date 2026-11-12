package com.chronoslife.radar

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private data class Sector(val id: String, val name: String)
private val sectors = listOf(Sector("ai-tech", "AI e tecnologia"), Sector("operations", "Industria e Operations"), Sector("sport", "Sport e innovazione"))
private data class Trend(val topic: String, val count: Int, val sources: Int, val status: String)
private sealed interface RadarState {
    data object Loading : RadarState
    data class Ready(val trends: List<Trend>, val dataStatus: String) : RadarState
    data class Failed(val message: String) : RadarState
}

private suspend fun loadTrends(sector: String, days: Int): RadarState = withContext(Dispatchers.IO) {
    try {
        val endpoint = "${BuildConfig.API_BASE_URL}/v1/trends?sector_id=$sector&window_days=$days"
        val connection = URL(endpoint).openConnection() as HttpURLConnection
        connection.connectTimeout = 8000
        connection.readTimeout = 8000
        connection.requestMethod = "GET"
        try {
            if (connection.responseCode != 200) return@withContext RadarState.Failed("Server HTTP ${connection.responseCode}")
            val json = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            val array = json.getJSONArray("items")
            val trends = (0 until array.length()).map { i ->
                val item = array.getJSONObject(i)
                Trend(item.getString("topic"), item.getInt("evidence_count"), item.getInt("independent_source_labels"), item.optString("score_status", "non disponibile"))
            }
            RadarState.Ready(trends, json.optString("data_status", "insufficient"))
        } finally { connection.disconnect() }
    } catch (e: Exception) { RadarState.Failed(e.localizedMessage ?: "Connessione non disponibile") }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { RadarApp() } }
    }
}

@Composable
private fun RadarApp() {
    var selected by remember { mutableIntStateOf(0) }
    var days by remember { mutableIntStateOf(90) }
    var refresh by remember { mutableIntStateOf(0) }
    var state by remember { mutableStateOf<RadarState>(RadarState.Loading) }
    LaunchedEffect(selected, days, refresh) {
        state = RadarState.Loading
        state = loadTrends(sectors[selected].id, days)
    }
    Scaffold(topBar = { Surface(tonalElevation = 2.dp) {
        Text("ChronosLife Radar", Modifier.padding(20.dp), style = MaterialTheme.typography.headlineSmall)
    } }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Segnali emergenti, con fonti verificabili", style = MaterialTheme.typography.titleMedium)
            ScrollableTabRow(selectedTabIndex = selected) {
                sectors.forEachIndexed { index, sector ->
                    Tab(selected = selected == index, onClick = { selected = index }, text = { Text(sector.name) })
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(30, 90, 365).forEach { value ->
                    FilterChip(selected = days == value, onClick = { days = value }, label = { Text("${value}g") })
                }
            }
            Button(onClick = { refresh++ }) { Text("Aggiorna Radar") }
            when (val result = state) {
                RadarState.Loading -> { CircularProgressIndicator(); Text("Caricamento evidenze…") }
                is RadarState.Failed -> {
                    Text("Backend non raggiungibile", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.titleMedium)
                    Text(result.message)
                    Text("Avvia il backend FastAPI e verifica l'indirizzo API. Nell'emulatore Android: 10.0.2.2; sul telefono: IP LAN del PC.")
                }
                is RadarState.Ready -> {
                    if (result.trends.isEmpty()) {
                        Text("Nessuna evidenza disponibile per questo settore e periodo.")
                        Text("Nessuna previsione viene generata senza dati verificabili.")
                    } else {
                        Text("${result.trends.size} argomenti con evidenze · Stato: ${result.dataStatus}", style = MaterialTheme.typography.bodySmall)
                        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(result.trends) { trend ->
                                Card(Modifier.fillMaxWidth()) {
                                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                        Text(trend.topic, style = MaterialTheme.typography.titleMedium)
                                        Text("Evidenze: ${trend.count} · Fonti dichiarate: ${trend.sources}")
                                        Text("Momentum: non calcolato (${trend.status})", style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}